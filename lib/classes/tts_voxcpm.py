import os
from pathlib import Path
import re
import warnings
# warnings.filterwarnings("ignore", category=FutureWarning, module="torchaudio")
# warnings.filterwarnings("ignore", category=UserWarning, module="torchaudio")
# warnings.filterwarnings("ignore", category=DeprecationWarning, module="torchaudio")
warnings.filterwarnings("ignore")

import torch
import numpy as np
import soundfile as sf
import torchaudio
from voxcpm import VoxCPM

from lib import models
from lib.classes.tts_engines.common.audio_filters import is_audio_data_valid, trim_audio
from lib.classes.tts_engines.common.utils import append_sentence2vtt
from lib.conf import default_audio_proc_format
from lib.models import TTS_ENGINES

class TTSVoxCPM:
    def __init__(self, session):
        self.session = session
        self.sample_rate = models[ "voxcpm" ]["internal"]["samplerate"]
        self.audio_segments = []
        self.sentences_total_time = 0.0
        self.sentence_idx = 1
        self.vtt_path = os.path.join(self.session['process_dir'], Path(self.session['final_name']).stem + '.vtt')    
        self.model = None

    def load_model(self):
        try:
            self.model = VoxCPM.from_pretrained("openbmb/VoxCPM-0.5B")
            return True
        except Exception as e:
            print(f"Error loading VoxCPM model: {e}")
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
    
    def generate_audio(self, sentence_number, sentence, prompt_wav_path, prompt_text):
        try:
            if self.model is None:
                if not self.load_model():
                    return None

            audio_sentence = self.model.generate(
                text=sentence,
                prompt_wav_path=prompt_wav_path,
                prompt_text=prompt_text,
                cfg_value=self.session['cfg_value'],
                inference_timesteps=self.session['inference_timesteps'],
                normalize=self.session['normalize'],
                denoise=self.session['denoise'],
                retry_badcase=self.session['retry_badcase'],
                retry_badcase_max_times=self.session['retry_badcase_max_times'],
                retry_badcase_ratio_threshold=self.session['retry_badcase_ratio_threshold'],
            )
            final_sentence_file = os.path.join(self.session['chapters_dir_sentences'], f'{sentence_number}.{default_audio_proc_format}')
            trim_audio_buffer = 0.004
            if is_audio_data_valid(audio_sentence):
                sourceTensor = self._tensor_type(audio_sentence)
                audio_tensor = sourceTensor.clone().detach().unsqueeze(0).cpu()
                if sentence[-1].isalnum() or sentence[-1] == '—':
                    audio_tensor = trim_audio(audio_tensor.squeeze(), self.sample_rate, 0.003, trim_audio_buffer).unsqueeze(0)
                self.audio_segments.append(audio_tensor)
                if not re.search(r'\w$', sentence, flags=re.UNICODE):
                    silence_time = int(np.random.uniform(0.3, 0.6) * 100) / 100
                    break_tensor = torch.zeros(1, int(self.sample_rate * silence_time))
                    self.audio_segments.append(break_tensor.clone())
                if self.audio_segments:
                    audio_tensor = torch.cat(self.audio_segments, dim=-1)
                    start_time = self.sentences_total_time
                    duration = round((audio_tensor.shape[-1] / self.sample_rate), 2)
                    end_time = start_time + duration
                    self.sentences_total_time = end_time
                    sentence_obj = {
                        "start": start_time,
                        "end": end_time,
                        "text": sentence,
                        "resume_check": self.sentence_idx
                    }
                    self.sentence_idx = append_sentence2vtt(sentence_obj, self.vtt_path)
                    if self.sentence_idx:
                        torchaudio.save(final_sentence_file, audio_tensor, self.sample_rate, format=default_audio_proc_format)
                        del audio_tensor
                self.audio_segments = []
                if os.path.exists(final_sentence_file):
                    return True
                else:
                    error = f"Cannot create {final_sentence_file}"
                    print(error)
            return False        
        except Exception as e:
            print(f"Error generating audio with VoxCPM: {e}")
            return False
