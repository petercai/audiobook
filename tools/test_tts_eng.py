from TTS.tts.utils.text.phonemizers.multi_phonemizer import MultiPhonemizer

# Define only English and Chinese phonemizers
custom_phonemizer_map = {
    "en-us": "espeak",
    "zh-cn": "espeak"
}
from TTS.api import TTS

# Initialize your multi-phonemizer
multi_phonemizer = MultiPhonemizer(lang_to_phonemizer_name=custom_phonemizer_map)

# Load TTS model (replace with your model name)
tts = TTS(model_name="models/tts/models--coqui--XTTS-v2", progress_bar=False, gpu=True)

# Patch or replace phonemizer in the TTS model (example, may require digging into internals)
tts.tts_model.phonemizer = multi_phonemizer

# Now run inference specifying language codes "en-us" or "zh-cn"
text_en = "Hello, this is an English sentence."
text_zh = "这是一个中文句子。"

wav_en = tts.tts(text_en, language="en-us")
wav_zh = tts.tts(text_zh, language="zh-cn")
