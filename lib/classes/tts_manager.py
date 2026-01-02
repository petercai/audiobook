import os
from pathlib import Path

from lib.models import TTS_ENGINES
from lib.util import util
from lib.conf import default_audio_proc_format


class TTSManager:
    """
    Manages the selection and initialization of different TTS engines.

    This class acts as a factory and a facade for various TTS implementations.
    It reads the 'tts_engine' from the session configuration and loads the
    appropriate engine, such as Coqui or VOXCPM.

    Required session values:
    - 'tts_engine': Specifies which TTS engine to load.
    - ... plus any session values required by the selected TTS engine.

    For Coqui engines, the following session values are used:
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
        Initializes the TTSManager.

        Args:
            session (dict): The session dictionary containing configuration.
        """
        self.session = session
        self.tts = None
        self._build()
 
    def _build(self):
        if self.session['tts_engine'] in TTS_ENGINES.values():
            if self.session['tts_engine'] in [TTS_ENGINES['XTTSv2'], TTS_ENGINES['BARK'], TTS_ENGINES['VITS'], TTS_ENGINES['FAIRSEQ'], TTS_ENGINES['TACOTRON2'], TTS_ENGINES['YOURTTS'], TTS_ENGINES['COSYVOICE']]:
                from lib.classes.tts_engines.coqui import Coqui
                self.tts = Coqui(self.session)
            elif self.session['tts_engine'] == TTS_ENGINES['VOXCPM']:
                from lib.classes.tts_voxcpm import TTSVoxCPM
                self.tts = TTSVoxCPM(self.session)
            elif self.session['tts_engine'] == TTS_ENGINES['INDEXTTS']:
                from lib.classes.tts_indextts import TTSIndexTTS
                self.tts = TTSIndexTTS(self.session)
            #elif self.session['tts_engine'] in [TTS_ENGINES['NEW_TTS']]:
            #    from lib.classes.tts_engines.new_tts import NewTts
            #    self.tts = NewTts(self.session)
            if self.tts:
                return True
            else:
                error = 'TTS engine could not be created!'
                print(error)
        else:
            print('Other TTS engines coming soon!')
        return False

    def convert_sentence2audio(self, sentence_number, sentence):
        try:
            if self.session['tts_engine'] in TTS_ENGINES.values():
                if self.session['tts_engine'] == TTS_ENGINES['VOXCPM']:
                    prompt_wav_path, prompt_text = self.init_voice_info(self.session.get('voice'))
                    return self.tts.generate_audio(sentence_number, sentence, prompt_wav_path, prompt_text)
                elif self.session['tts_engine'] == TTS_ENGINES['INDEXTTS']:
                    prompt_wav_path = self.session.get('voice')
                    final_sentence_file = os.path.join(self.session['chapters_dir_sentences'], f'{sentence_number}.{default_audio_proc_format}')
                    return self.tts.synthesize(sentence, prompt_wav_path, final_sentence_file)
                else:
                    return self.tts.convert(sentence_number, sentence)
            else:
                print('Other TTS engines coming soon!')    
        except Exception as e:
            error = f'convert_sentence2audio(): {e}'
            util.print_error(error)
            raise ValueError(e)
        return False

    def init_voice_info(self, voice_path):
        prompt_text_path = Path(voice_path).with_suffix(".txt")
        # prompt_text = "无论是互联网巨头还是刚起步的创业公司都在竞相努力成为元宇宙这条充满无限可能性赛道的领先者事实确实这些平台除了产品发布发新闻稿时热度高很快就回归平静就像horizon world一样"  # You might want to make this configurable
        if prompt_text_path.exists():
            with open(prompt_text_path, 'r', encoding='utf-8') as f:
                prompt_text = f.read().strip()
        else:
            raise FileNotFoundError(f"Prompt text file not found: {prompt_text_path}")

        return voice_path, prompt_text
