import os
import torch
import numpy as np
import soundfile as sf
from voxcpm import VoxCPM

class TTSVoxCPM:
    def __init__(self, session):
        self.session = session
        self.model = None

    def load_model(self):
        try:
            self.model = VoxCPM.from_pretrained("openbmb/VoxCPM-0.5B")
            return True
        except Exception as e:
            print(f"Error loading VoxCPM model: {e}")
            return False

    def generate_audio(self, text, prompt_wav_path, prompt_text):
        try:
            if self.model is None:
                if not self.load_model():
                    return None

            wav = self.model.generate(
                text=text,
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
            # shoue return ture or false
            return wav
        except Exception as e:
            print(f"Error generating audio with VoxCPM: {e}")
            return None
