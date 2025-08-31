import pytest
import torch
from TTS.api import TTS

@pytest.fixture
def xtts():
    # Get device
    device = "cuda" if torch.cuda.is_available() else "cpu"
    # Initialize TTS
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
    return tts
  
@pytest.fixture
def input_text_zh():
  return "二愣子睁大着双眼，直直望着茅草和烂泥糊成的黑屋顶，身上盖着的旧棉被，已呈深黄色，看不出原来的本来面目，还若有若无的散发着淡淡的霉味。"

@pytest.fixture
def speaker_wav_yunjian():
  return "voices/zho/adult/male/yunjian_24000.wav"

@pytest.fixture
def speaker_wav_yunxi():
  return "voices/zho/adult/male/yunxi_24000.wav"

@pytest.fixture
def speaker_wav_yunyi():
  return "voices/zho/adult/female/yunyi_24000.wav"

def test_gen_chinese_voice_file(xtts, input_text_zh, speaker_wav_yunjian, speaker_wav_yunxi, speaker_wav_yunyi): 
  # TTS to a file, use a preset speaker
  xtts.tts_to_file(
    text=input_text_zh,
    speaker_wav=speaker_wav_yunyi,
    language="zh-cn",
    file_path="output_yunyi_god.wav",
    split_sentences=True
  )
  
def test_gen_en_voice_file(xtts):
  # TTS to a file, use a preset speaker
  xtts.tts_to_file(
    text="The big ball of yellow might be spilling into the clouds, runny and yolky and blurring into the bluest sky, bright with cold hope and false promises about fond memories, real families, hearty breakfasts, stacks of pancakes drizzled in maple syrup sitting on a plate in a world that doesn’t exist anymore.",
    speaker_wav="voices/eng/adult/female/AlexandraHisakawa.wav",
    language="en",
    file_path="output_en_Alexandra.wav",
    split_sentences=True
  )
