import soundfile as sf
import numpy as np
import pytest
from voxcpm import VoxCPM

@pytest.fixture
def voxcpm_config():
    return {
        "text_path": "ebooks/god-1.txt",
        "prompt_text": "无论是互联网巨头还是刚起步的创业公司都在竞相努力成为元宇宙这条充满无限可能性赛道的领先者事实确实这些平台除了产品发布发新闻稿时热度高很快就回归平静就像horizon world一样",
        "prompt_wav_path": "voices/zho/adult/male/yunjian.wav",
        "output_wav": "yunjian_god-1.wav",
        "sample_rate": 16000,
    }
    
@pytest.fixture
def voxcpm_config_yunxiao():
    return {
        "text_path": "ebooks/god-1.txt",
        "prompt_text": "无论是互联网巨头还是刚起步的创业公司都在竞相努力成为元宇宙这条充满无限可能性赛道的领先者事实确实这些平台除了产品发布发新闻稿时热度高很快就回归平静就像horizon world一样",
        "prompt_wav_path": "voices/zho/adult/female/yunxiao.wav",
        "output_wav": "yunxiao_god-1.wav",
        "sample_rate": 16000,
    }
    
@pytest.fixture
def voxcpm_config_alex():
    return {
        "text_path": "ebooks/UnravelMe_one_sentense.txt",
        "prompt_wav_path": "voices/eng/adult/female/AlexandraHisakawa.wav",      # optional: path to a prompt speech for voice cloning
        "prompt_text": "Alexandra Hizakawa, an XTS Engine built-in voice, ready to speak for any kind of text. A big juicy fish jumps quickly, vexed, the dwarf whacks my zippered box.",          # optional: reference text
        "output_wav": "alex_UnravelMe-1.wav",
        "sample_rate": 16000,
    }

@pytest.fixture
def voxcpm_model():
    return VoxCPM.from_pretrained("openbmb/VoxCPM-0.5B")

def test_voxcpm_generate(voxcpm_model, voxcpm_config_alex):
    
    tts_model = voxcpm_model
    tts_config = voxcpm_config_alex
    # Read text from file
    with open(tts_config["text_path"], "r", encoding="utf-8") as f:
        text = f.read()

        wav = tts_model.generate(
            text=text,
            prompt_wav_path=tts_config["prompt_wav_path"],
            prompt_text=tts_config["prompt_text"],
            cfg_value=2.0,
            inference_timesteps=10,
            normalize=True,
            denoise=True,
            retry_badcase=True,
            retry_badcase_max_times=3,
            retry_badcase_ratio_threshold=6.0,
        )

        sf.write(tts_config["output_wav"], wav, tts_config["sample_rate"])
        assert isinstance(wav, np.ndarray)
        assert wav.size > 0
        print(f"saved: {tts_config['output_wav']}")

