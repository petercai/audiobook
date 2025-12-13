import os
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

import torch
import numpy as np
import soundfile as sf
from indextts.infer_v2 import IndexTTS2

from lib import models
from lib.classes.tts_engines.common.audio_filters import is_audio_data_valid, trim_audio
from lib.classes.tts_engines.common.utils import append_sentence2vtt
from lib.conf import default_audio_proc_format
from lib.conf import models_dir
from lib.models import TTS_ENGINES, default_engine_settings

class TTSIndexTTS:
    """
    A class for Text-to-Speech using IndexTTS.
    """
    def __init__(self, session):
        """
        Initializes the TTSIndexTTS class.

        Args:
            session (dict): The session dictionary.
        """
        self.session = session
        self.sample_rate = models.default_engine_settings[TTS_ENGINES['INDEXTTS']]['samplerate']
        self.audio_segments = []
        self.sentences_total_time = 0.0
        self.sentence_idx = 1
        self.vtt_path = os.path.join(self.session['process_dir'], Path(self.session['final_name']).stem + '.vtt')
        self.model = None

        # Set default IndexTTS parameters
        self.session['temperature'] = default_engine_settings[TTS_ENGINES['INDEXTTS']]['temperature']
        self.session['top_p'] = default_engine_settings[TTS_ENGINES['INDEXTTS']]['top_p']
        self.session['top_k'] = default_engine_settings[TTS_ENGINES['INDEXTTS']]['top_k']
        self.session['speed'] = default_engine_settings[TTS_ENGINES['INDEXTTS']]['speed']

    def load_model(self):
        """
        Loads the IndexTTS model.

        Returns:
            bool: True if the model is loaded successfully, False otherwise.
        """
        try:
            model_dir_path = os.path.join(models_dir, "tts")
            cfg_path = os.path.join(model_dir_path, "config.yaml")
            
            # Get offline_mode from command line, default to True if not specified
            offline_mode = self.session.get('offline_mode', True)

            self.model = IndexTTS2(
                cfg_path=cfg_path,
                model_dir=model_dir_path,
                use_fp16=torch.cuda.is_available(),
                use_cuda_kernel=torch.cuda.is_available(),
                offline_mode=offline_mode
            )
            return True
        except Exception as e:
            print(f"Error loading IndexTTS model: {e}")
            return False

    def _tensor_type(self, audio_data):
        """
        Converts audio data to a torch.Tensor.

        Args:
            audio_data (torch.Tensor or np.ndarray or list): The audio data.

        Returns:
            torch.Tensor: The audio data as a tensor.
        """
        if isinstance(audio_data, torch.Tensor):
            return audio_data
        elif isinstance(audio_data, np.ndarray):
            return torch.from_numpy(audio_data).float()
        elif isinstance(audio_data, list):
            return torch.tensor(audio_data, dtype=torch.float32)
        else:
            raise TypeError(f"Unsupported type for audio_data: {type(audio_data)}")

    def synthesize(self, text: str, voice_path: str, output_path: str) -> bool:
        """
        Synthesizes audio from text using the IndexTTS model.

        Args:
            text (str): The text to synthesize.
            voice_path (str): The path to the voice prompt audio file.
            output_path (str): The path to save the synthesized audio file.

        Returns:
            bool: True if synthesis is successful, False otherwise.
        """
        try:
            if self.model is None:
                if not self.load_model():
                    return False
            
            # IndexTTS does not directly support temperature, top_k, top_p, and speed parameters.
            # These parameters are kept for compatibility with the UI, but they are not used in the inference.
            # The following lines are placeholders and have no effect on the output.
            # temperature = self.session['temperature']
            # top_p = self.session['top_p']
            # top_k = self.session['top_k']
            # speed = self.session['speed']

            self.model.infer(spk_audio_prompt=voice_path, text=text, output_path=output_path)
            
            if os.path.exists(output_path):
                audio_data, sr = sf.read(output_path)
                if is_audio_data_valid(audio_data):
                    source_tensor = self._tensor_type(audio_data).unsqueeze(0)
                    # The audio is already saved by tts.infer, so we just need to process it for VTT
                    start_time = self.sentences_total_time
                    duration = round((source_tensor.shape[-1] / self.sample_rate), 2)
                    end_time = start_time + duration
                    self.sentences_total_time = end_time
                    sentence_obj = {
                        "start": start_time,
                        "end": end_time,
                        "text": text,
                        "resume_check": self.sentence_idx
                    }
                    self.sentence_idx = append_sentence2vtt(sentence_obj, self.vtt_path)
                    return True
            return False
        except Exception as e:
            print(f"Error generating audio with IndexTTS: {e}")
            return False
