import hashlib, math, os, shutil, subprocess, tempfile, threading, uuid, warnings
# warnings.filterwarnings("ignore", category=FutureWarning, module="torchaudio")
# warnings.filterwarnings("ignore", category=UserWarning, module="torchaudio")
# warnings.filterwarnings("ignore", category=DeprecationWarning, module="torchaudio")
warnings.filterwarnings("ignore")
import numpy as np, regex as re, soundfile as sf, torch, torchaudio

from huggingface_hub import hf_hub_download
from pathlib import Path
from pprint import pprint

from lib import *
from lib.functions import DependencyError
from lib.classes.tts_engines.common.utils import unload_tts, append_sentence2vtt
from lib.classes.tts_engines.common.audio_filters import detect_gender, trim_audio, normalize_audio, is_audio_data_valid

#import logging
#logging.basicConfig(level=logging.DEBUG)

lock = threading.Lock()

class Coqui:
    """
    Coqui TTS engine implementation.

    This class handles the initialization, model loading, and speech synthesis using various Coqui TTS engines
    such as XTTSv2, Bark, VITS, FAIRSEQ, TACOTRON2, and YOURTTS. It manages voice cloning, audio processing,
    and conversion of text sentences to audio segments.

    Required session values:
    - tts_engine: The TTS engine to use (e.g., 'XTTSv2', 'Bark').
    - fine_tuned: Specifies if fine-tuned models are used.
    - device: Device for computation ('cuda' or 'cpu').
    - custom_model: Name of the custom model if applicable.
    - custom_model_dir: Directory for custom models.
    - language: Language code for synthesis.
    - voice: Path to the voice file or speaker name.
    - process_dir: Directory for processing output.
    - final_name: Name of the final output file.
    - language_iso1: ISO-1 language code.
    - temperature: (optional) Temperature for sampling.
    - length_penalty: (optional) Penalty for output length.
    - num_beams: (optional) Number of beams for beam search.
    - repetition_penalty: (optional) Penalty for repetition.
    - top_k: (optional) Top-k sampling parameter.
    - top_p: (optional) Top-p sampling parameter.
    - speed: (optional) Speaking speed.
    - enable_text_splitting: (optional) Enable text splitting.
    - text_temp: (optional) Text temperature for Bark.
    - waveform_temp: (optional) Waveform temperature for Bark.
    """

    def __init__(self, session):
        """
        Initializes the Coqui TTS engine with the provided session configuration.

        This constructor sets up internal parameters, caches, and builds the TTS model based on the session settings.

        Args:
            session (dict): A dictionary containing configuration settings for the TTS engine.
        """
        try:
            self.session = session
            self.cache_dir = tts_dir
            self.speakers_path = None
            self.xtts_builtin_speakers_list = None
            self.tts_key = f"{self.session['tts_engine']}-{self.session['fine_tuned']}"
            self.tts_vc_key = default_vc_model.rsplit('/', 1)[-1]
            self.is_bf16 = True if self.session['device'] == 'cuda' and torch.cuda.is_bf16_supported() == True else False
            self.npz_path = None
            self.npz_data = None
            self.sentences_total_time = 0.0
            self.sentence_idx = 1
            self.params = {
                TTS_ENGINES['XTTSv2']: {"latent_embedding": {}},
                TTS_ENGINES['BARK']: {},
                TTS_ENGINES['VITS']: {"semitones": {}},
                TTS_ENGINES['FAIRSEQ']: {"semitones": {}},
                TTS_ENGINES['TACOTRON2']: {"semitones": {}},
                TTS_ENGINES['YOURTTS']: {},
                TTS_ENGINES['COSYVOICE']: {"zero_shot_speakers": {}}
            }
            self.params[self.session['tts_engine']]['samplerate'] = models[self.session['tts_engine']][self.session['fine_tuned']]['samplerate']
            self.vtt_path = os.path.join(self.session['process_dir'], Path(self.session['final_name']).stem + '.vtt')    
            self.resampler_cache = {}
            self.audio_segments = []
            self._build()
        except Exception as e:
            error = f'__init__() error: {e}'
            print(error)
            return None

    def _build(self):
        """
        Initializes and loads the appropriate TTS (Text-to-Speech) model based on the session settings.

        This method is the central hub for model loading. It checks which TTS engine is selected
        and whether a custom or pre-trained model should be used. It handles downloading models
        from Hugging Face Hub, loading them into memory, and preparing them for synthesis.

        Returns:
            TTS model instance or False: Returns the loaded TTS engine instance if successful,
                                         otherwise returns False on failure.
        """
        try:
            tts_engine_name = self.session['tts_engine']
            load_zeroshot = tts_engine_name in [TTS_ENGINES['VITS'], TTS_ENGINES['FAIRSEQ'], TTS_ENGINES['TACOTRON2']]
            tts = loaded_tts.get(self.tts_key, {}).get('engine', False)

            if not tts:
                xtt_sv_files_ = default_engine_settings[TTS_ENGINES['XTTSv2']]['files']
                self._ensure_xtts_speakers(xtt_sv_files_)

                fine_tuned_ = self.session['fine_tuned']
                tuned_files_ = models[tts_engine_name][fine_tuned_]['files']
                custom_model_ = self.session['custom_model']
                handlers = self._engine_handlers(fine_tuned_, tuned_files_, custom_model_, xtt_sv_files_)
                for handler in handlers:
                    if handler():
                        break

            tts_loaded = (loaded_tts.get(self.tts_key) or {}).get('engine', False)

            if tts_loaded and load_zeroshot:
                tts_vc = (loaded_tts.get(self.tts_vc_key) or {}).get('engine', False)
                if not tts_vc and self.session['voice'] is not None:
                    print(f"Loading TTS {self.tts_vc_key} zeroshot model, it takes a while, please be patient...")
                    tts_vc = self._load_api(self.tts_vc_key, default_vc_model, self.session['device'])
            
            return tts_loaded
        except Exception as e:
            print(f'build() error: {e}')
            return False

    def _engine_handlers(self, fine_tuned_, tuned_files_, custom_model_, xtt_sv_files_):
        """
        Returns a list of engine handler callables. Each handler returns True when it has
        processed (or attempted to process) the current engine, and False when the engine
        does not match. This lets us chain handlers without a long if/elif block.
        """
        return [
            lambda: self._handle_cosyvoice(fine_tuned_, tuned_files_, custom_model_),
            lambda: self._handle_xttsv2(fine_tuned_, tuned_files_, custom_model_, xtt_sv_files_),
            lambda: self._handle_bark(fine_tuned_, tuned_files_, custom_model_),
            lambda: self._handle_vits(fine_tuned_, custom_model_),
            lambda: self._handle_fairseq(fine_tuned_, custom_model_),
            lambda: self._handle_tacotron2(fine_tuned_, custom_model_),
            lambda: self._handle_yourtts(fine_tuned_, custom_model_),
        ]

    def _handle_cosyvoice(self, fine_tuned_, tuned_files_, custom_model_):
        """
        Load CosyVoice checkpoints (zero-shot or SFT) from the local tts_dir layout.

        CosyVoice ships as two flavours:
        - CosyVoice2-0.5B: zero-shot speaker cloning (needs a prompt wav + optional text).
        - CosyVoice-300M-SFT: fine-tuned multi-speaker model with fixed speaker IDs.
        """
        if self.session['tts_engine'] != TTS_ENGINES['COSYVOICE']:
            return False

        if custom_model_ is not None:
            print(f"{TTS_ENGINES['COSYVOICE']} custom model not implemented yet!")
            return True

        # Keep the tts_key unique per CosyVoice flavour to reuse cached models.
        self._cosy_repo = models[TTS_ENGINES['COSYVOICE']][fine_tuned_]['repo']
        self.tts_key = f"{TTS_ENGINES['COSYVOICE']}-{self._cosy_repo}"
        if (loaded_tts.get(self.tts_key) or {}).get('engine'):
            return True

        model_dir = os.path.join(tts_dir, self._cosy_repo)
        unload_tts(self.session['device'], [self.tts_key, self.tts_vc_key])
        try:
            fp16=torch.cuda.is_available()
            if self._cosy_repo == 'CosyVoice-300M-SFT':
                from cosyvoice.cli.cosyvoice import CosyVoice
                tts = CosyVoice(model_dir, load_jit=False, load_trt=False, fp16=fp16)
            else:
                from cosyvoice.cli.cosyvoice import CosyVoice2
                tts = CosyVoice2(model_dir, load_jit=False, load_trt=False, load_vllm=False, fp16=fp16)
        except Exception as e:
            print(f"{TTS_ENGINES['COSYVOICE']} load error: {e}")
            return True

        if tts:
            self.params[TTS_ENGINES['COSYVOICE']]['samplerate'] = getattr(
                tts, "sample_rate", self.params[TTS_ENGINES['COSYVOICE']]['samplerate']
            )
            loaded_tts[self.tts_key] = {"engine": tts, "config": None}
            print(f'{self} Loaded!')
            return True
        return False

    def _ensure_xtts_speakers(self, xtt_sv_files_):
        if self.xtts_builtin_speakers_list is not None:
            return
        repo_ = models[TTS_ENGINES['XTTSv2']]['internal']['repo']
        try:
            self.speakers_path = hf_hub_download(
                repo_id=repo_,
                filename=xtt_sv_files_[4],
                cache_dir=self.cache_dir,
                local_files_only=self.session['offline_mode'])
            self.xtts_builtin_speakers_list = torch.load(
                self.speakers_path,
                map_location=self.session['device'],
                weights_only=False
            )
        except Exception as e:
            if self.session['offline_mode']:
                print(f"Offline mode: Failed to load XTTSv2 speakers file. Expected in '{self.cache_dir}'.")
            raise e

    def _handle_xttsv2(self, fine_tuned_, tuned_files_, custom_model_, xtt_sv_files_):
        if self.session['tts_engine'] != TTS_ENGINES['XTTSv2']:
            return False

        print(f"Loading TTS {TTS_ENGINES['XTTSv2']} model, it takes a while, please be patient...")
        if custom_model_ is not None:
            custom_model_dir_ = self.session['custom_model_dir']
            config_path = os.path.join(custom_model_dir_, TTS_ENGINES['XTTSv2'], custom_model_, xtt_sv_files_[0])
            checkpoint_path = os.path.join(custom_model_dir_, TTS_ENGINES['XTTSv2'], custom_model_, xtt_sv_files_[1])
            vocab_path = os.path.join(custom_model_dir_, TTS_ENGINES['XTTSv2'], custom_model_, xtt_sv_files_[2])
            self.tts_key = f"{TTS_ENGINES['XTTSv2']}-{custom_model_}"
            self._load_checkpoint(tts_engine=TTS_ENGINES['XTTSv2'], key=self.tts_key, checkpoint_path=checkpoint_path, config_path=config_path, vocab_path=vocab_path, device=self.session['device'])
            return True

        hf_repo = models[TTS_ENGINES['XTTSv2']][fine_tuned_]['repo']
        hf_sub = '' if fine_tuned_ == 'internal' else models[TTS_ENGINES['XTTSv2']][fine_tuned_]['sub']
        try:
            config_path = hf_hub_download(
                repo_id=hf_repo,
                filename=f"{hf_sub}{tuned_files_[0]}",
                cache_dir=self.cache_dir,
                local_files_only=self.session['offline_mode'])
            checkpoint_path = hf_hub_download(
                repo_id=hf_repo,
                filename=f"{hf_sub}{tuned_files_[1]}",
                cache_dir=self.cache_dir,
                local_files_only=self.session['offline_mode'])
            vocab_path = hf_hub_download(
                repo_id=hf_repo,
                filename=f"{hf_sub}{tuned_files_[2]}",
                cache_dir=self.cache_dir,
                local_files_only=self.session['offline_mode'])
        except Exception as e:
            if self.session['offline_mode']:
                print(f"Offline mode: Failed to load XTTSv2 model files from '{hf_repo}'. Expected in '{self.cache_dir}'.")
            raise e
        self._load_checkpoint(tts_engine=TTS_ENGINES['XTTSv2'], key=self.tts_key, checkpoint_path=checkpoint_path, config_path=config_path, vocab_path=vocab_path, device=self.session['device'])
        return True

    def _handle_bark(self, fine_tuned_, tuned_files_, custom_model_):
        if self.session['tts_engine'] != TTS_ENGINES['BARK']:
            return False

        if custom_model_ is not None:
            print(f"{TTS_ENGINES['BARK']} custom model not implemented yet!")
            return True

        hf_repo = models[TTS_ENGINES['BARK']][fine_tuned_]['repo']
        hf_sub = models[TTS_ENGINES['BARK']][fine_tuned_]['sub']
        try:
            text_model_path = hf_hub_download(repo_id=hf_repo, filename=f"{hf_sub}{tuned_files_[0]}", cache_dir=self.cache_dir, local_files_only=self.session['offline_mode'])
        except Exception as e:
            if self.session['offline_mode']:
                print(f"Offline mode: Failed to load BARK model file from '{hf_repo}'. Expected in '{self.cache_dir}'.")
            raise e
        checkpoint_dir = os.path.dirname(text_model_path)
        self._load_checkpoint(tts_engine=TTS_ENGINES['BARK'], key=self.tts_key, checkpoint_dir=checkpoint_dir, device=self.session['device'])
        return True

    def _handle_vits(self, fine_tuned_, custom_model_):
        if self.session['tts_engine'] != TTS_ENGINES['VITS']:
            return False

        if custom_model_ is not None:
            print(f"{TTS_ENGINES['VITS']} custom model not implemented yet!")
            return True

        iso_dir = language_tts[TTS_ENGINES['VITS']][self.session['language']]
        sub_dict = models[TTS_ENGINES['VITS']][fine_tuned_]['sub']
        sub = next((key for key, lang_list in sub_dict.items() if iso_dir in lang_list), None)
        if sub is None:
            print(f"{TTS_ENGINES['VITS']} checkpoint for {self.session['language']} not found!")
            return True

        self.params[TTS_ENGINES['VITS']]['samplerate'] = models[TTS_ENGINES['VITS']][fine_tuned_]['samplerate'][sub]
        model_path = models[TTS_ENGINES['VITS']][fine_tuned_]['repo'].replace("[lang_iso1]", iso_dir).replace("[xxx]", sub)
        print(f"Loading TTS {model_path} model, it takes a while, please be patient...")
        self.tts_key = model_path
        self._load_api(self.tts_key, model_path, self.session['device'])
        return True

    def _handle_fairseq(self, fine_tuned_, custom_model_):
        if self.session['tts_engine'] != TTS_ENGINES['FAIRSEQ']:
            return False

        if custom_model_ is not None:
            print(f"{TTS_ENGINES['FAIRSEQ']} custom model not implemented yet!")
            return True

        model_path = models[TTS_ENGINES['FAIRSEQ']][fine_tuned_]['repo'].replace("[lang]", self.session['language'])
        self.tts_key = model_path
        self._load_api(self.tts_key, model_path, self.session['device'])
        return True

    def _handle_tacotron2(self, fine_tuned_, custom_model_):
        if self.session['tts_engine'] != TTS_ENGINES['TACOTRON2']:
            return False

        if custom_model_ is not None:
            print(f"{TTS_ENGINES['TACOTRON2']} custom model not implemented yet!")
            return True

        iso_dir = language_tts[TTS_ENGINES['TACOTRON2']][self.session['language']]
        sub_dict = models[TTS_ENGINES['TACOTRON2']][fine_tuned_]['sub']
        sub = next((key for key, lang_list in sub_dict.items() if iso_dir in lang_list), None)
        self.params[TTS_ENGINES['TACOTRON2']]['samplerate'] = models[TTS_ENGINES['TACOTRON2']][fine_tuned_]['samplerate'][sub]
        if sub is None:
            iso_dir = self.session['language']
            sub = next((key for key, lang_list in sub_dict.items() if iso_dir in lang_list), None)
        if sub is None:
            print(f"{TTS_ENGINES['TACOTRON2']} checkpoint for {self.session['language']} not found!")
            return True

        model_path = models[TTS_ENGINES['TACOTRON2']][fine_tuned_]['repo'].replace("[lang_iso1]", iso_dir).replace("[xxx]", sub)
        print(f"Loading TTS {model_path} model, it takes a while, please be patient...")
        self.tts_key = model_path
        self._load_api(self.tts_key, model_path, self.session['device'])
        return True

    def _handle_yourtts(self, fine_tuned_, custom_model_):
        if self.session['tts_engine'] != TTS_ENGINES['YOURTTS']:
            return False

        if custom_model_ is not None:
            print(f"{TTS_ENGINES['YOURTTS']} custom model not implemented yet!")
            return True

        model_path = models[TTS_ENGINES['YOURTTS']][fine_tuned_]['repo']
        self._load_api(self.tts_key, model_path, self.session['device'])
        return True

    def _load_api(self, key, model_path, device):
        """
        Loads a TTS model using the Coqui TTS API.

        This method handles the loading of TTS models that are directly supported by the
        `TTS.api`. It checks if the model is already cached, unloads other models to
        free up resources if necessary, and then initializes the new model. The loaded
        model is stored in a global cache for future use.

        Args:
            key (str): A unique key to identify the model in the cache.
            model_path (str): The path or name of the model to be loaded by the API.
            device (str): The device to load the model onto ('cuda' or 'cpu').

        Returns:
            TTS model instance or False: The loaded TTS model instance on success,
                                         or False on failure.
        """
        global lock
        try:
            # Check if the model is already loaded in the global cache.
            if key in loaded_tts.keys():
                return loaded_tts[key]['engine']
            
            # Unload existing TTS models to free up memory before loading a new one.
            unload_tts(device, [self.tts_key, self.tts_vc_key])
            
            # Import the Coqui TTS API class.
            from TTS.api import TTS as coquiAPI
            
            # Use a lock to ensure thread-safe model loading.
            with lock:
                # Initialize the TTS model from the specified model path.
                tts = coquiAPI(model_path)
                
                if tts:
                    # Move the model to the specified device (GPU or CPU).
                    if device == 'cuda':
                        tts.cuda()
                    else:
                        tts.to(device)
                    
                    # Cache the loaded model instance for future use.
                    loaded_tts[key] = {"engine": tts, "config": None} 
                    msg = f'{model_path} Loaded!'
                    print(msg)
                    return tts
                else:
                    # Handle cases where the TTS engine could not be created.
                    error = 'TTS engine could not be created!'
                    print(error)
        except Exception as e:
            # Catch and report any exceptions during the loading process.
            error = f'_load_api() error: {e}'
            print(error)
        
        # Return False if the model could not be loaded.
        return False

    def _load_checkpoint(self, **kwargs):
        """
        Loads a TTS model from a checkpoint file.

        This method is responsible for loading models that require manual setup from
        configuration and checkpoint files, such as XTTSv2 and Bark. It handles
        model-specific initialization, configuration, and checkpoint loading.

        Args:
            **kwargs: A dictionary of keyword arguments containing model-specific
                      parameters like 'key', 'tts_engine', 'device', 'checkpoint_path', etc.

        Returns:
            TTS model instance or False: The loaded TTS model instance on success,
                                         or False on failure.
        """
        global lock
        try:
            # Extract the unique key for the model from kwargs.
            key = kwargs.get('key')
            # If the model is already in the cache, return the existing instance.
            if key in loaded_tts.keys():
                return loaded_tts[key]['engine']
            
            # Extract TTS engine type and device from kwargs.
            tts_engine = kwargs.get('tts_engine')
            device = kwargs.get('device')
            
            # Unload any previously loaded models to free up resources.
            unload_tts(device, [self.tts_key, self.tts_vc_key])
            
            # Use a lock to ensure thread-safe model loading.
            with lock:
                # --- XTTSv2 Model Loading ---
                if tts_engine == TTS_ENGINES['XTTSv2']:
                    from TTS.tts.configs.xtts_config import XttsConfig
                    from TTS.tts.models.xtts import Xtts
                    
                    # Get paths for checkpoint, config, and vocabulary files.
                    checkpoint_path = kwargs.get('checkpoint_path')
                    config_path = kwargs.get('config_path', None)
                    vocab_path = kwargs.get('vocab_path', None)
                    
                    # Initialize and load the model configuration.
                    config = XttsConfig()
                    config.models_dir = os.path.join("models", "tts")
                    config.load_json(config_path)
                    
                    # Initialize the XTTS model from the configuration.
                    tts = Xtts.init_from_config(config)
                    # Load the model weights from the checkpoint.
                    tts.load_checkpoint(
                        config,
                        checkpoint_path=checkpoint_path,
                        vocab_path=vocab_path,
                        use_deepspeed=default_engine_settings[TTS_ENGINES['XTTSv2']]['use_deepspeed'],
                        eval=True
                    )
                # --- Bark Model Loading ---
                elif tts_engine == TTS_ENGINES['BARK']:
                    import numpy
                    import torch.serialization
                    # Add safe globals for torch serialization to handle numpy types.
                    torch.serialization.add_safe_globals([
                        (numpy._core.multiarray.scalar, 'numpy.core.multiarray.scalar'),
                        numpy.dtype,
                        numpy.dtypes.Float64DType
                    ])
                    from TTS.tts.configs.bark_config import BarkConfig
                    from TTS.tts.models.bark import Bark
                    
                    # Get the directory containing the Bark model checkpoints.
                    checkpoint_dir = kwargs.get('checkpoint_dir')
                    
                    # Initialize and configure the Bark model.
                    config = BarkConfig()
                    config.CACHE_DIR = self.cache_dir
                    config.USE_SMALLER_MODELS = os.environ.get('SUNO_USE_SMALL_MODELS', '').lower() == 'true'
                    
                    # Initialize the Bark model from the configuration.
                    tts = Bark.init_from_config(config)
                    # Load the model weights from the checkpoint directory.
                    tts.load_checkpoint(
                        config,
                        checkpoint_dir=checkpoint_dir,
                        eval=True
                    )                    
            
            # After loading, move the model to the specified device and cache it.
            if tts:
                if device == 'cuda':
                    tts.cuda()
                else:
                    tts.to(device)
                
                # Store the loaded model and its config in the global cache.
                loaded_tts[key] = {"engine": tts, "config": config}
                msg = f'{tts_engine} Loaded!'
                print(msg)
                return tts
            else:
                # Handle cases where the TTS engine could not be created.
                error = 'TTS engine could not be created!'
                print(error)
        except Exception as e:
            # Catch and report any exceptions during the loading process.
            error = f'_load_checkpoint() error: {e}'
            print(error)
        
        # Return False if loading fails.
        return False

    def _check_xtts_builtin_speakers(self, voice_path, speaker, device):
        """
        Checks if a built-in XTTS speaker needs to be converted to a different language and performs the conversion.

        This function is used when a built-in English speaker is selected for a non-English language.
        It generates a new voice sample in the target language using the selected speaker's characteristics
        and saves it to the appropriate language directory.

        Args:
            voice_path (str): The file path of the original speaker voice.
            speaker (str): The name of the speaker.
            device (str): The device to run the TTS model on ('cuda' or 'cpu').

        Returns:
            str or bool: The path to the newly generated voice file if successful,
                         the original voice_path if no conversion is needed, or False on error.
        """
        try:
            voice_parts = Path(voice_path).parts
            # --- Condition Check ---
            # Determine if conversion is necessary. This is true if:
            # 1. The target language is not already in the voice path.
            # 2. The speaker is not a Bark voice (this function is XTTS-specific).
            # 3. The target language is not English.
            if (self.session['language'] not in voice_parts
                    and speaker not in default_engine_settings[TTS_ENGINES['BARK']]['voices'].keys()
                    and self.session['language'] != 'eng'):
                # Check if the target language is supported by XTTSv2.
                if self.session['language'] in language_tts[TTS_ENGINES['XTTSv2']].keys():
                    # --- Default Text Loading ---
                    # Load a default text in the target language to be synthesized.
                    default_text_file = os.path.join(voices_dir, self.session['language'], 'default.txt')
                    if os.path.exists(default_text_file):
                        print(f"Converting builtin eng voice to {self.session['language']}...")
                        
                        # --- Model Loading ---
                        # Load the internal XTTSv2 model for the conversion.
                        tts_internal_key = f"{TTS_ENGINES['XTTSv2']}-internal"
                        default_text = Path(default_text_file).read_text(encoding="utf-8")
                        hf_repo = models[TTS_ENGINES['XTTSv2']]['internal']['repo']
                        hf_sub = ''
                        tts = (loaded_tts.get(tts_internal_key) or {}).get('engine', False)
                        if not tts:
                            # Unload other models to free up memory before loading the new one.
                            for key in list(loaded_tts.keys()):
                                unload_tts(device, None, key)
                            try:
                                config_path = hf_hub_download(
                                    repo_id=hf_repo,
                                    filename=f"{hf_sub}{models[TTS_ENGINES['XTTSv2']]['internal']['files'][0]}",
                                    cache_dir=self.cache_dir,
                                    local_files_only=self.session['offline_mode'])
                                checkpoint_path = hf_hub_download(
                                    repo_id=hf_repo,
                                    filename=f"{hf_sub}{models[TTS_ENGINES['XTTSv2']]['internal']['files'][1]}",
                                    cache_dir=self.cache_dir,
                                    local_files_only=self.session['offline_mode'])
                                vocab_path = hf_hub_download(
                                    repo_id=hf_repo,
                                    filename=f"{hf_sub}{models[TTS_ENGINES['XTTSv2']]['internal']['files'][2]}",
                                    cache_dir=self.cache_dir,
                                    local_files_only=self.session['offline_mode'])
                            except Exception as e:
                                if self.session['offline_mode']:
                                    print(f"Offline mode: Failed to load internal XTTSv2 model files from '{hf_repo}'. Expected in '{self.cache_dir}'.")
                                raise e
                            tts = self._load_checkpoint(tts_engine=TTS_ENGINES['XTTSv2'], key=tts_internal_key, checkpoint_path=checkpoint_path, config_path=config_path, vocab_path=vocab_path, device=device)
                        
                        if tts:
                            # --- Speaker Latent Calculation ---
                            # Get the conditioning latents for the speaker.
                            voices__keys = default_engine_settings[TTS_ENGINES['XTTSv2']]['voices'].keys()
                            if speaker in voices__keys:
                                # Use pre-computed latents for built-in speakers.
                                speaker_ = default_engine_settings[TTS_ENGINES['XTTSv2']]['voices'][speaker]
                                gpt_cond_latent, speaker_embedding = self.xtts_builtin_speakers_list[speaker_].values()
                            else:
                                # Compute latents from the voice audio file for custom speakers.
                                gpt_cond_latent, speaker_embedding = tts.get_conditioning_latents(audio_path=[voice_path])
                            
                            # --- Inference ---
                            # Set fine-tuning parameters from the session.
                            fine_tuned_params = {
                                key: cast_type(self.session[key])
                                for key, cast_type in {
                                    "temperature": float,
                                    "length_penalty": float,
                                    "num_beams": int,
                                    "repetition_penalty": float,
                                    "top_k": int,
                                    "top_p": float,
                                    "speed": float,
                                    "enable_text_splitting": bool
                                }.items()
                                if self.session.get(key) is not None
                            }
                            
                            # Run TTS inference to generate the audio.
                            with torch.no_grad():
                                result = tts.inference(
                                    text=default_text,
                                    language=self.session['language_iso1'],
                                    gpt_cond_latent=gpt_cond_latent,
                                    speaker_embedding=speaker_embedding,
                                    **fine_tuned_params
                                )
                            
                            # --- Audio Processing and Saving ---
                            audio_data = result.get('wav')
                            if audio_data is not None:
                                audio_data = audio_data.tolist()
                                sourceTensor = self._tensor_type(audio_data)
                                audio_tensor = sourceTensor.clone().detach().unsqueeze(0).cpu()
                                
                                # Create the new path for the converted voice.
                                lang_dir = 'con-' if self.session['language'] == 'con' else self.session['language']
                                new_voice_path = re.sub(r'([\\/])eng([\\/])', rf'\1{lang_dir}\2', voice_path)
                                proc_voice_path = new_voice_path.replace('.wav', '_temp.wav')
                                
                                # Save the temporary audio file.
                                torchaudio.save(proc_voice_path, audio_tensor, default_engine_settings[TTS_ENGINES['XTTSv2']]['samplerate'], format='wav')
                                
                                # Normalize the audio and save to the final path.
                                if normalize_audio(proc_voice_path, new_voice_path, default_audio_proc_samplerate):
                                    del audio_data, sourceTensor, audio_tensor
                                    # --- Cleanup ---
                                    # Unload the internal model if it's not the main TTS engine.
                                    if self.session['tts_engine'] != TTS_ENGINES['XTTSv2']:
                                        del tts
                                        unload_tts(device, None, tts_internal_key)
                                    return new_voice_path
                                else:
                                    error = 'normalize_audio() error'
                            else:
                                error = f'No audio waveform found in _check_xtts_builtin_speakers() result: {result}'
                        else:
                            error = f"_check_xtts_builtin_speakers() error: {TTS_ENGINES['XTTSv2']} model could not be loaded"
                    else:
                        error = f'The default text file {default_text_file} could not be found! Voice cloning will stay in English.'
                    print(error)
                else:
                    # If language is not supported by XTTSv2, return original path.
                    return voice_path
            else:
                # If no conversion is needed, return the original path.
                return voice_path
        except Exception as e:
            error = f'_check_xtts_builtin_speakers() error: {e}'
            print(error)
        return False

    def _check_bark_npz(self, voice_path, bark_dir, speaker, device):
        try:
            if self.session['language'] in language_tts[TTS_ENGINES['BARK']].keys():
                npz_dir = os.path.join(bark_dir, speaker)
                npz_file = os.path.join(npz_dir, f'{speaker}.npz')
                if os.path.exists(npz_file):
                    return True
                else:
                    os.makedirs(npz_dir, exist_ok=True)
                    tts_internal_key = f"{TTS_ENGINES['BARK']}-internal"
                    hf_repo = models[TTS_ENGINES['BARK']]['internal']['repo']
                    hf_sub = models[TTS_ENGINES['BARK']]['internal']['sub']
                    tts = (loaded_tts.get(tts_internal_key) or {}).get('engine', False)
                    if not tts:
                        for key in list(loaded_tts.keys()): unload_tts(device, None, key)
                        try:
                            text_model_path = hf_hub_download(
                                repo_id=hf_repo,
                                filename=f"{hf_sub}{models[TTS_ENGINES['BARK']]['internal']['files'][0]}",
                                cache_dir=self.cache_dir,
                                local_files_only=self.session['offline_mode'])
                            hf_hub_download(
                                repo_id=hf_repo,
                                filename=f"{hf_sub}{models[TTS_ENGINES['BARK']]['internal']['files'][1]}",
                                cache_dir=self.cache_dir,
                                local_files_only=self.session['offline_mode'])
                            hf_hub_download(
                                repo_id=hf_repo,
                                filename=f"{hf_sub}{models[TTS_ENGINES['BARK']]['internal']['files'][2]}",
                                cache_dir=self.cache_dir,
                                local_files_only=self.session['offline_mode'])
                        except Exception as e:
                            if self.session['offline_mode']:
                                print(f"Offline mode: Failed to load internal BARK model files from '{hf_repo}'. Expected in '{self.cache_dir}'.")
                            raise e
                        checkpoint_dir = os.path.dirname(text_model_path)
                        tts = self._load_checkpoint(tts_engine=TTS_ENGINES['BARK'], key=tts_internal_key, checkpoint_dir=checkpoint_dir, device=device)
                    if tts:
                        voice_temp = os.path.splitext(npz_file)[0]+'.wav'
                        shutil.copy(voice_path, voice_temp)
                        default_text_file = os.path.join(voices_dir, self.session['language'], 'default.txt')
                        default_text = Path(default_text_file).read_text(encoding="utf-8")
                        fine_tuned_params = {
                            key: cast_type(self.session[key])
                            for key, cast_type in {
                                "text_temp": float,
                                "waveform_temp": float
                            }.items()
                            if self.session.get(key) is not None
                        }
                        with torch.no_grad():
                            torch.manual_seed(67878789)
                            audio_data = tts.synthesize(
                                default_text,
                                loaded_tts[tts_internal_key]['config'],
                                speaker_id=speaker,
                                voice_dirs=bark_dir,
                                silent=True,
                                **fine_tuned_params
                            )
                        os.remove(voice_temp)
                        del audio_data
                        if self.session['tts_engine'] != TTS_ENGINES['BARK']:
                            del tts
                            unload_tts(device, None, tts_internal_key)
                        msg = f"Saved NPZ file: {npz_file}"
                        print(msg)
                        return True
                    else:
                        error = f'_check_bark_npz() error: {tts_internal_key} is False'
                        print(error)
            else:
                return True
        except Exception as e:
            error = f'_check_bark_npz() error: {e}'
            print(error)
        return False
        
    def _tensor_type(self, audio_data):
        if isinstance(audio_data, torch.Tensor):
            return audio_data
        elif isinstance(audio_data, np.ndarray):  
            return torch.from_numpy(audio_data).float()
        elif isinstance(audio_data, list):  
            return torch.tensor(audio_data, dtype=torch.float32)
        else:
            raise TypeError(f"Unsupported type for audio_data: {type(audio_data)}")
            
    def _get_resampler(self, orig_sr, target_sr):
        key = (orig_sr, target_sr)
        if key not in self.resampler_cache:
            self.resampler_cache[key] = torchaudio.transforms.Resample(
                orig_freq=orig_sr, new_freq=target_sr
            )
        return self.resampler_cache[key]

    def _resample_wav(self, wav_path, expected_sr):
        waveform, orig_sr = torchaudio.load(wav_path)
        if orig_sr == expected_sr and waveform.size(0) == 1:
            return wav_path
        if waveform.size(0) > 1:
            waveform = waveform.mean(dim=0, keepdim=True)
        if orig_sr != expected_sr:
            resampler = self._get_resampler(orig_sr, expected_sr)
            waveform = resampler(waveform)
        wav_tensor = waveform.squeeze(0)
        wav_numpy = wav_tensor.cpu().numpy()
        tmp_fh = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path = tmp_fh.name
        tmp_fh.close()
        sf.write(tmp_path, wav_numpy, expected_sr, subtype="PCM_16")
        return tmp_path

    def _synth_handlers(self):
        """
        Returns a mapping between TTS engine keys and their synthesis callables.
        This avoids long if/elif chains and makes it easy to plug in new engines.
        """
        return {
            TTS_ENGINES['XTTSv2']: lambda tts, sentence, settings, speaker: self._synthesize_xtts(tts, sentence, settings, speaker),
            TTS_ENGINES['BARK']: lambda tts, sentence, settings, speaker: self._synthesize_bark(tts, sentence, settings, speaker),
            TTS_ENGINES['VITS']: lambda tts, sentence, settings, speaker: self._synthesize_vits_family(tts, sentence, settings, speaker, TTS_ENGINES['VITS']),
            TTS_ENGINES['FAIRSEQ']: lambda tts, sentence, settings, speaker: self._synthesize_vits_family(tts, sentence, settings, speaker, TTS_ENGINES['FAIRSEQ']),
            TTS_ENGINES['TACOTRON2']: lambda tts, sentence, settings, speaker: self._synthesize_vits_family(tts, sentence, settings, speaker, TTS_ENGINES['TACOTRON2']),
            TTS_ENGINES['YOURTTS']: lambda tts, sentence, settings, speaker: self._synthesize_yourtts(tts, sentence, settings, speaker),
            TTS_ENGINES['COSYVOICE']: lambda tts, sentence, settings, speaker: self._synthesize_cosyvoice(tts, sentence, settings, speaker),
        }

    def _synthesize_xtts(self, tts, sentence, settings, speaker):
        trim_audio_buffer = 0.008
        if settings['voice_path'] is not None and settings['voice_path'] in settings['latent_embedding'].keys():
            settings['gpt_cond_latent'], settings['speaker_embedding'] = settings['latent_embedding'][settings['voice_path']]
        else:
            msg = 'Computing speaker latents...'
            print(msg)
            if speaker in default_engine_settings[TTS_ENGINES['XTTSv2']]['voices'].keys():
                settings['gpt_cond_latent'], settings['speaker_embedding'] = self.xtts_builtin_speakers_list[
                    default_engine_settings[TTS_ENGINES['XTTSv2']]['voices'][speaker]
                ].values()
            else:
                settings['gpt_cond_latent'], settings['speaker_embedding'] = tts.get_conditioning_latents(audio_path=[settings['voice_path']])
            settings['latent_embedding'][settings['voice_path']] = settings['gpt_cond_latent'], settings['speaker_embedding']

        fine_tuned_params = {
            key: cast_type(self.session[key])
            for key, cast_type in {
                "temperature": float, "length_penalty": float, "num_beams": int,
                "repetition_penalty": float, "top_k": int, "top_p": float,
                "speed": float, "enable_text_splitting": bool
            }.items() if self.session.get(key) is not None
        }

        with torch.no_grad():
            result = tts.inference(
                text=sentence.replace('.', ' —'),
                language=self.session['language_iso1'],
                gpt_cond_latent=settings['gpt_cond_latent'],
                speaker_embedding=settings['speaker_embedding'],
                **fine_tuned_params
            )
        audio_sentence = result.get('wav')
        return audio_sentence.tolist() if is_audio_data_valid(audio_sentence) else None, trim_audio_buffer

    def _synthesize_bark(self, tts, sentence, settings, speaker):
        trim_audio_buffer = 0.002
        if speaker in default_engine_settings[self.session['tts_engine']]['voices'].keys():
            bark_dir = default_engine_settings[self.session['tts_engine']]['speakers_path']
        else:
            bark_dir = os.path.join(os.path.dirname(settings['voice_path']), 'bark')
            if not self._check_bark_npz(settings['voice_path'], bark_dir, speaker, self.session['device']):
                print('Could not create npz file!')
                return None, trim_audio_buffer

        npz_file = os.path.join(bark_dir, speaker, f'{speaker}.npz')
        fine_tuned_params = {
            key: cast_type(self.session[key])
            for key, cast_type in {"text_temp": float, "waveform_temp": float}.items()
            if self.session.get(key) is not None
        }
        if self.npz_path is None or self.npz_path != npz_file:
            self.npz_path = npz_file
            self.npz_data = np.load(self.npz_path, allow_pickle=True)

        history_prompt = [
            self.npz_data["semantic_prompt"],
            self.npz_data["coarse_prompt"],
            self.npz_data["fine_prompt"]
        ]

        with torch.no_grad():
            torch.manual_seed(67878789)
            audio_sentence, _ = tts.generate_audio(
                sentence,
                history_prompt=history_prompt,
                silent=True,
                **fine_tuned_params
            )
        return audio_sentence.tolist() if is_audio_data_valid(audio_sentence) else None, trim_audio_buffer

    def _synthesize_vits_family(self, tts, sentence, settings, speaker, engine_key):
        trim_audio_buffer = 0.004
        speaker_argument = {}
        if engine_key == TTS_ENGINES['VITS']:
            if self.session['language'] == 'eng' and 'vctk/vits' in models[self.session['tts_engine']]['internal']['sub']:
                speaker_argument = {"speaker": 'p262'}
            elif self.session['language'] == 'cat' and 'custom/vits' in models[self.session['tts_engine']]['internal']['sub']:
                speaker_argument = {"speaker": '09901'}

        if settings['voice_path'] is not None:
            proc_dir = os.path.join(self.session['voice_dir'], 'proc')
            os.makedirs(proc_dir, exist_ok=True)
            tmp_in_wav = os.path.join(proc_dir, f"{uuid.uuid4()}.wav")
            tmp_out_wav = os.path.join(proc_dir, f"{uuid.uuid4()}.wav")

            processed_sentence = sentence
            if engine_key == TTS_ENGINES['FAIRSEQ']:
                processed_sentence = re.sub(re.compile(r"[.:—]"), ' ', sentence)
            elif engine_key == TTS_ENGINES['TACOTRON2']:
                processed_sentence = re.sub(re.compile(r'["—]'), '', sentence)

            tts.tts_to_file(text=processed_sentence, file_path=tmp_in_wav, **speaker_argument)

            if settings['voice_path'] in settings['semitones'].keys():
                semitones = settings['semitones'][settings['voice_path']]
            else:
                voice_path_gender = detect_gender(settings['voice_path'])
                voice_builtin_gender = detect_gender(tmp_in_wav)
                semitones = 0
                if voice_builtin_gender != voice_path_gender:
                    semitones = -4 if voice_path_gender == 'male' else 4
                settings['semitones'][settings['voice_path']] = semitones

            if semitones != 0:
                try:
                    cmd = [shutil.which('sox'), tmp_in_wav, "-r", str(settings['samplerate']), tmp_out_wav, "pitch", str(semitones * 100)]
                    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except (subprocess.CalledProcessError, FileNotFoundError) as e:
                    DependencyError(e)
                    return None, trim_audio_buffer
            else:
                tmp_out_wav = tmp_in_wav

            tts_vc = (loaded_tts.get(self.tts_vc_key) or {}).get('engine', False)
            if tts_vc:
                settings['samplerate'] = TTS_VOICE_CONVERSION[self.tts_vc_key]['samplerate']
                source_wav = self._resample_wav(tmp_out_wav, settings['samplerate'])
                target_wav = self._resample_wav(settings['voice_path'], settings['samplerate'])
                audio_sentence = tts_vc.voice_conversion(source_wav=source_wav, target_wav=target_wav)
            else:
                return None, trim_audio_buffer

            for f in [tmp_in_wav, tmp_out_wav, source_wav]:
                if os.path.exists(f): os.remove(f)
        else:
            audio_sentence = tts.tts(text=sentence, **speaker_argument)

        return audio_sentence, trim_audio_buffer

    def _synthesize_yourtts(self, tts, sentence, settings, speaker):
        trim_audio_buffer = 0.004
        language = self.session['language_iso1'] if self.session['language_iso1'] in ['en', 'fr', 'pt'] else 'en'
        if settings['voice_path'] is not None:
            speaker_argument = {"speaker_wav": settings['voice_path']}
        else:
            speaker_argument = {"speaker": default_engine_settings[TTS_ENGINES['YOURTTS']]['voices']['ElectroMale-2']}

        with torch.no_grad():
            audio_sentence = tts.tts(text=sentence.replace('—', '').strip(), language=language, **speaker_argument)
        return audio_sentence, trim_audio_buffer

    def _synthesize_cosyvoice(self, tts, sentence, settings, speaker):
        """
        Run CosyVoice inference for either zero-shot (CosyVoice2) or SFT speakers.

        The generator returns chunks; we concatenate them to keep behaviour consistent
        with the other engines before trimming/saving in convert().
        """
        trim_audio_buffer = 0.004
        try:
            samplerate = settings.get('samplerate', default_engine_settings[TTS_ENGINES['COSYVOICE']]['samplerate'])
            audio_chunks = []
            if self._cosy_repo == 'CosyVoice-300M-SFT':
                # Fine-tuned CosyVoice uses fixed speaker ids instead of reference audio.
                speaker_id = speaker or models[TTS_ENGINES['COSYVOICE']][self.session['fine_tuned']]['voice']
                for out in tts.inference_sft(sentence, speaker_id, stream=False):
                    audio_chunks.append(out['tts_speech'])
            else:
                # Zero-shot CosyVoice2 path leverages a prompt wav + optional prompt text.
                voice_path = settings.get('voice_path')
                if voice_path is None or not os.path.exists(voice_path):
                    print('CosyVoice zero-shot requires a valid reference voice file.')
                    return None, trim_audio_buffer
                from cosyvoice.utils.file_utils import load_wav
                prompt_audio = load_wav(voice_path, 16000)
                prompt_text = ''
                prompt_text_file = Path(voice_path).with_suffix(".txt")
                if prompt_text_file.exists():
                    prompt_text = prompt_text_file.read_text(encoding="utf-8").strip()
                zero_cache = settings.setdefault('zero_shot_speakers', {})
                speaker_id = zero_cache.get(voice_path)
                if speaker_id is None:
                    speaker_id = f"cosy_{hashlib.md5(voice_path.encode('utf-8')).hexdigest()[:8]}"
                    added = tts.add_zero_shot_spk(prompt_text, prompt_audio, speaker_id)
                    if not added:
                        print('Failed to register CosyVoice zero-shot speaker.')
                        return None, trim_audio_buffer
                    zero_cache[voice_path] = speaker_id
                for out in tts.inference_zero_shot(sentence, prompt_text, prompt_audio, zero_shot_spk_id=speaker_id, stream=False):
                    audio_chunks.append(out['tts_speech'])

            if not audio_chunks:
                return None, trim_audio_buffer
            settings['samplerate'] = getattr(tts, "sample_rate", samplerate)
            speech = torch.cat(audio_chunks, dim=1)
            return speech.squeeze(0), trim_audio_buffer
        except Exception as e:
            print(f"_synthesize_cosyvoice() error: {e}")
            return None, trim_audio_buffer

    def convert(self, s_n, s):
        """
        Converts a single sentence to audio using the loaded TTS model.

        This is the core method for speech synthesis. It takes a sentence number and the
        sentence text, then uses the appropriate TTS engine to generate audio. It handles
        special commands like breaks and pauses, manages voice cloning and conversion,
        and processes the final audio output.

        Args:
            s_n (int): The sentence number, used for naming the output file.
            s (str): The text of the sentence to be converted.

        Returns:
            bool: True if the conversion is successful and the audio file is saved,
                  False otherwise.
        """
        try:
            # --- Initialization ---
            sentence_number = s_n
            sentence = s
            speaker = None
            audio_data = False
            trim_audio_buffer = 0.004  # Default trim buffer
            
            # Get settings for the current TTS engine.
            settings = self.params[self.session['tts_engine']]
            final_sentence_file = os.path.join(self.session['chapters_dir_sentences'], f'{sentence_number}.{default_audio_proc_format}')
            
            cosyvoice_sft = (
                self.session['tts_engine'] == TTS_ENGINES['COSYVOICE']
                and self.session['fine_tuned'] == 'CosyVoice-300M-SFT'
            )
            if cosyvoice_sft:
                # SFT flavour uses speaker IDs instead of reference audio.
                speaker = self.session['voice'] or models[self.session['tts_engine']][self.session['fine_tuned']]['voice']
                if not speaker:
                    # Fallback to the first declared CosyVoice speaker id.
                    speaker = next(iter(default_engine_settings[TTS_ENGINES['COSYVOICE']]['voices'].values()), None)
                settings['voice_path'] = None
            else:
                # --- Voice Path Determination ---
                # Determine the path to the voice file to be used for synthesis.
                settings['voice_path'] = (
                    self.session['voice'] if self.session['voice'] is not None 
                    else os.path.join(self.session['custom_model_dir'], self.session['tts_engine'], self.session['custom_model'], 'ref.wav') if self.session['custom_model'] is not None
                    else models[self.session['tts_engine']][self.session['fine_tuned']]['voice']
                )
                
                # --- Speaker and Voice Pre-processing ---
                if settings['voice_path'] is not None:
                    # Extract the speaker name from the voice file path.
                    speaker = re.sub(r'\.wav$', '', os.path.basename(settings['voice_path']))
                    
                    # Check if a built-in XTTS speaker needs to be converted to a different language.
                    if (
                        self.session['tts_engine'] != TTS_ENGINES['COSYVOICE']
                        and settings['voice_path'] not in default_engine_settings[TTS_ENGINES['BARK']]['voices'].keys()
                        and os.path.basename(settings['voice_path']) != 'ref.wav'
                    ):
                        self.session['voice'] = settings['voice_path'] = self._check_xtts_builtin_speakers(settings['voice_path'], speaker, self.session['device'])
                        if not settings['voice_path']:
                            msg = f"Could not create the builtin speaker selected voice in {self.session['language']}"
                            print(msg)
                            return False
            
            # Get the loaded TTS engine from the cache.
            tts = (loaded_tts.get(self.tts_key) or {}).get('engine', False)
            
            if tts:
                # --- Handle Special Commands (Breaks and Pauses) ---
                if sentence == TTS_SML['break']:
                    silence_time = int(np.random.uniform(0.3, 0.6) * 100) / 100
                    break_tensor = torch.zeros(1, int(settings['samplerate'] * silence_time))
                    self.audio_segments.append(break_tensor.clone())
                    return True
                elif sentence == TTS_SML['pause']:
                    silence_time = int(np.random.uniform(1.0, 1.8) * 100) / 100
                    pause_tensor = torch.zeros(1, int(settings['samplerate'] * silence_time))
                    self.audio_segments.append(pause_tensor.clone())
                    return True
                else:
                    # --- Sentence Pre-processing ---
                    # Add a pause marker if the sentence ends with an alphanumeric character.
                    if sentence[-1].isalnum():
                        sentence = f'{sentence} —'
                    handlers = self._synth_handlers()
                    synth_func = handlers.get(self.session['tts_engine'])
                    if synth_func is None:
                        print(f"convert() error: Unsupported engine {self.session['tts_engine']}")
                        return False

                    audio_sentence, trim_audio_buffer = synth_func(tts, sentence, settings, speaker)
                    
                    # --- Final Audio Processing ---
                    if is_audio_data_valid(audio_sentence):
                        # Convert audio data to a tensor.
                        sourceTensor = self._tensor_type(audio_sentence)
                        audio_tensor = sourceTensor.clone().detach().unsqueeze(0).cpu()
                        
                        # Trim silence from the end of the audio.
                        if sentence[-1].isalnum() or sentence[-1] == '—':
                            audio_tensor = trim_audio(audio_tensor.squeeze(), settings['samplerate'], 0.003, trim_audio_buffer).unsqueeze(0)
                        
                        # Append the processed audio segment.
                        self.audio_segments.append(audio_tensor)
                        
                        # Add a short break after sentences that don't end with a word character.
                        if not re.search(r'\w$', sentence, flags=re.UNICODE):
                            silence_time = int(np.random.uniform(0.3, 0.6) * 100) / 100
                            break_tensor = torch.zeros(1, int(settings['samplerate'] * silence_time))
                            self.audio_segments.append(break_tensor.clone())
                        
                        # --- Save and Finalize ---
                        if self.audio_segments:
                            # Concatenate all audio segments for the final output.
                            audio_tensor = torch.cat(self.audio_segments, dim=-1)
                            
                            # Calculate timing information for the VTT file.
                            start_time = self.sentences_total_time
                            duration = round((audio_tensor.shape[-1] / settings['samplerate']), 2)
                            end_time = start_time + duration
                            self.sentences_total_time = end_time
                            
                            # Create and append the sentence object to the VTT file.
                            sentence_obj = {"start": start_time, "end": end_time, "text": sentence, "resume_check": self.sentence_idx}
                            self.sentence_idx = append_sentence2vtt(sentence_obj, self.vtt_path)
                            
                            # Save the final audio file.
                            if self.sentence_idx:
                                torchaudio.save(final_sentence_file, audio_tensor, settings['samplerate'], format=default_audio_proc_format)
                                del audio_tensor

                        # Reset audio segments for the next sentence.
                        self.audio_segments = []
                        
                        if os.path.exists(final_sentence_file):
                            return True
                        else:
                            print(f"Cannot create {final_sentence_file}")
            else:
                print(f"convert() error: {self.session['tts_engine']} is None")
        except Exception as e:
            raise ValueError(f'Coqui.convert(): {e}')
        
        return False
