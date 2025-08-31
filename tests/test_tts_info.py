import torch
from TTS.api import TTS

# Get device
device = "cuda" if torch.cuda.is_available() else "cpu"

'''
-------------------------------- live log call --------------------------------
2025-08-31 18:14:29 [    INFO]  (manage.py:96)
2025-08-31 18:14:29 [    INFO] Name format: type/language/dataset/model (manage.py:97)
2025-08-31 18:14:29 [    INFO]   1: tts_models/multilingual/multi-dataset/xtts_v2 [already downloaded] (manage.py:105)
2025-08-31 18:14:29 [    INFO]   2: tts_models/multilingual/multi-dataset/xtts_v1.1 (manage.py:105)
2025-08-31 18:14:29 [    INFO]   3: tts_models/multilingual/multi-dataset/your_tts (manage.py:105)
2025-08-31 18:14:29 [    INFO]   4: tts_models/multilingual/multi-dataset/bark (manage.py:105)
2025-08-31 18:14:29 [    INFO]   5: tts_models/bg/cv/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]   6: tts_models/cs/cv/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]   7: tts_models/da/cv/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]   8: tts_models/et/cv/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]   9: tts_models/ga/cv/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]  10: tts_models/en/ek1/tacotron2 (manage.py:105)
2025-08-31 18:14:29 [    INFO]  11: tts_models/en/ljspeech/tacotron2-DDC (manage.py:105)
2025-08-31 18:14:29 [    INFO]  12: tts_models/en/ljspeech/tacotron2-DDC_ph (manage.py:105)
2025-08-31 18:14:29 [    INFO]  13: tts_models/en/ljspeech/glow-tts (manage.py:105)
2025-08-31 18:14:29 [    INFO]  14: tts_models/en/ljspeech/speedy-speech (manage.py:105)
2025-08-31 18:14:29 [    INFO]  15: tts_models/en/ljspeech/tacotron2-DCA (manage.py:105)
2025-08-31 18:14:29 [    INFO]  16: tts_models/en/ljspeech/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]  17: tts_models/en/ljspeech/vits--neon (manage.py:105)
2025-08-31 18:14:29 [    INFO]  18: tts_models/en/ljspeech/fast_pitch (manage.py:105)
2025-08-31 18:14:29 [    INFO]  19: tts_models/en/ljspeech/overflow (manage.py:105)
2025-08-31 18:14:29 [    INFO]  20: tts_models/en/ljspeech/neural_hmm (manage.py:105)
2025-08-31 18:14:29 [    INFO]  21: tts_models/en/vctk/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]  22: tts_models/en/vctk/fast_pitch (manage.py:105)
2025-08-31 18:14:29 [    INFO]  23: tts_models/en/sam/tacotron-DDC (manage.py:105)
2025-08-31 18:14:29 [    INFO]  24: tts_models/en/blizzard2013/capacitron-t2-c50 (manage.py:105)
2025-08-31 18:14:29 [    INFO]  25: tts_models/en/blizzard2013/capacitron-t2-c150_v2 (manage.py:105)
2025-08-31 18:14:29 [    INFO]  26: tts_models/en/multi-dataset/tortoise-v2 (manage.py:105)
2025-08-31 18:14:29 [    INFO]  27: tts_models/en/jenny/jenny (manage.py:105)
2025-08-31 18:14:29 [    INFO]  28: tts_models/es/mai/tacotron2-DDC (manage.py:105)
2025-08-31 18:14:29 [    INFO]  29: tts_models/es/css10/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]  30: tts_models/fr/mai/tacotron2-DDC (manage.py:105)
2025-08-31 18:14:29 [    INFO]  31: tts_models/fr/css10/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]  32: tts_models/uk/mai/glow-tts (manage.py:105)
2025-08-31 18:14:29 [    INFO]  33: tts_models/uk/mai/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]  34: tts_models/zh-CN/baker/tacotron2-DDC-GST (manage.py:105)
2025-08-31 18:14:29 [    INFO]  35: tts_models/nl/mai/tacotron2-DDC (manage.py:105)
2025-08-31 18:14:29 [    INFO]  36: tts_models/nl/css10/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]  37: tts_models/de/thorsten/tacotron2-DCA (manage.py:105)
2025-08-31 18:14:29 [    INFO]  38: tts_models/de/thorsten/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]  39: tts_models/de/thorsten/tacotron2-DDC (manage.py:105)
2025-08-31 18:14:29 [    INFO]  40: tts_models/de/css10/vits-neon (manage.py:105)
2025-08-31 18:14:29 [    INFO]  41: tts_models/ja/kokoro/tacotron2-DDC (manage.py:105)
2025-08-31 18:14:29 [    INFO]  42: tts_models/tr/common-voice/glow-tts (manage.py:105)
2025-08-31 18:14:29 [    INFO]  43: tts_models/it/mai_female/glow-tts (manage.py:105)
2025-08-31 18:14:29 [    INFO]  44: tts_models/it/mai_female/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]  45: tts_models/it/mai_male/glow-tts (manage.py:105)
2025-08-31 18:14:29 [    INFO]  46: tts_models/it/mai_male/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]  47: tts_models/ewe/openbible/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]  48: tts_models/hau/openbible/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]  49: tts_models/lin/openbible/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]  50: tts_models/tw_akuapem/openbible/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]  51: tts_models/tw_asante/openbible/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]  52: tts_models/yor/openbible/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]  53: tts_models/hu/css10/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]  54: tts_models/el/cv/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]  55: tts_models/fi/css10/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]  56: tts_models/hr/cv/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]  57: tts_models/lt/cv/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]  58: tts_models/lv/cv/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]  59: tts_models/mt/cv/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]  60: tts_models/pl/mai_female/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]  61: tts_models/pt/cv/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]  62: tts_models/ro/cv/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]  63: tts_models/sk/cv/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]  64: tts_models/sl/cv/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]  65: tts_models/sv/cv/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]  66: tts_models/ca/custom/vits (manage.py:105)
2025-08-31 18:14:29 [    INFO]  67: tts_models/fa/custom/glow-tts (manage.py:105)
2025-08-31 18:14:29 [    INFO]  68: tts_models/fa/custom/vits-female (manage.py:105)
2025-08-31 18:14:29 [    INFO]  69: tts_models/bn/custom/vits-male (manage.py:105)
2025-08-31 18:14:29 [    INFO]  70: tts_models/bn/custom/vits-female (manage.py:105)
2025-08-31 18:14:29 [    INFO]  71: tts_models/be/common-voice/glow-tts (manage.py:105)
2025-08-31 18:14:29 [    INFO]  (manage.py:96)
2025-08-31 18:14:29 [    INFO] Name format: type/language/dataset/model (manage.py:97)
2025-08-31 18:14:29 [    INFO]   1: vocoder_models/universal/libri-tts/wavegrad (manage.py:105)
2025-08-31 18:14:29 [    INFO]   2: vocoder_models/universal/libri-tts/fullband-melgan (manage.py:105)
2025-08-31 18:14:29 [    INFO]   3: vocoder_models/en/ek1/wavegrad (manage.py:105)
2025-08-31 18:14:29 [    INFO]   4: vocoder_models/en/librispeech100/wavlm-hifigan (manage.py:105)
2025-08-31 18:14:29 [    INFO]   5: vocoder_models/en/librispeech100/wavlm-hifigan_prematched (manage.py:105)
2025-08-31 18:14:29 [    INFO]   6: vocoder_models/en/ljspeech/multiband-melgan (manage.py:105)
2025-08-31 18:14:29 [    INFO]   7: vocoder_models/en/ljspeech/hifigan_v2 (manage.py:105)
2025-08-31 18:14:29 [    INFO]   8: vocoder_models/en/ljspeech/univnet (manage.py:105)
2025-08-31 18:14:29 [    INFO]   9: vocoder_models/en/blizzard2013/hifigan_v2 (manage.py:105)
2025-08-31 18:14:29 [    INFO]  10: vocoder_models/en/vctk/hifigan_v2 (manage.py:105)
2025-08-31 18:14:29 [    INFO]  11: vocoder_models/en/sam/hifigan_v2 (manage.py:105)
2025-08-31 18:14:29 [    INFO]  12: vocoder_models/nl/mai/parallel-wavegan (manage.py:105)
2025-08-31 18:14:29 [    INFO]  13: vocoder_models/de/thorsten/wavegrad (manage.py:105)
2025-08-31 18:14:29 [    INFO]  14: vocoder_models/de/thorsten/fullband-melgan (manage.py:105)
2025-08-31 18:14:29 [    INFO]  15: vocoder_models/de/thorsten/hifigan_v1 (manage.py:105)
2025-08-31 18:14:29 [    INFO]  16: vocoder_models/ja/kokoro/hifigan_v1 (manage.py:105)
2025-08-31 18:14:29 [    INFO]  17: vocoder_models/uk/mai/multiband-melgan (manage.py:105)
2025-08-31 18:14:29 [    INFO]  18: vocoder_models/tr/common-voice/hifigan (manage.py:105)
2025-08-31 18:14:29 [    INFO]  19: vocoder_models/be/common-voice/hifigan (manage.py:105)
2025-08-31 18:14:29 [    INFO]  (manage.py:96)
2025-08-31 18:14:29 [    INFO] Name format: type/language/dataset/model (manage.py:97)
2025-08-31 18:14:29 [    INFO]   1: voice_conversion_models/multilingual/vctk/freevc24 (manage.py:105)
2025-08-31 18:14:29 [    INFO]   2: voice_conversion_models/multilingual/multi-dataset/knnvc (manage.py:105)
2025-08-31 18:14:29 [    INFO]   3: voice_conversion_models/multilingual/multi-dataset/openvoice_v1 (manage.py:105)
2025-08-31 18:14:29 [    INFO]   4: voice_conversion_models/multilingual/multi-dataset/openvoice_v2 (manage.py:105)
2025-08-31 18:14:29 [    INFO]  (manage.py:122)
2025-08-31 18:14:29 [    INFO] Path to downloaded models: C:\Users\caipe\AppData\Local\tts (manage.py:123)
tts_models/multilingual/multi-dataset/xtts_v2
tts_models/multilingual/multi-dataset/xtts_v1.1
tts_models/multilingual/multi-dataset/your_tts
tts_models/multilingual/multi-dataset/bark
tts_models/bg/cv/vits
tts_models/cs/cv/vits
tts_models/da/cv/vits
tts_models/et/cv/vits
tts_models/ga/cv/vits
tts_models/en/ek1/tacotron2
tts_models/en/ljspeech/tacotron2-DDC
tts_models/en/ljspeech/tacotron2-DDC_ph
tts_models/en/ljspeech/glow-tts
tts_models/en/ljspeech/speedy-speech
tts_models/en/ljspeech/tacotron2-DCA
tts_models/en/ljspeech/vits
tts_models/en/ljspeech/vits--neon
tts_models/en/ljspeech/fast_pitch
tts_models/en/ljspeech/overflow
tts_models/en/ljspeech/neural_hmm
tts_models/en/vctk/vits
tts_models/en/vctk/fast_pitch
tts_models/en/sam/tacotron-DDC
tts_models/en/blizzard2013/capacitron-t2-c50
tts_models/en/blizzard2013/capacitron-t2-c150_v2
tts_models/en/multi-dataset/tortoise-v2
tts_models/en/jenny/jenny
tts_models/es/mai/tacotron2-DDC
tts_models/es/css10/vits
tts_models/fr/mai/tacotron2-DDC
tts_models/fr/css10/vits
tts_models/uk/mai/glow-tts
tts_models/uk/mai/vits
tts_models/zh-CN/baker/tacotron2-DDC-GST
tts_models/nl/mai/tacotron2-DDC
tts_models/nl/css10/vits
tts_models/de/thorsten/tacotron2-DCA
tts_models/de/thorsten/vits
tts_models/de/thorsten/tacotron2-DDC
tts_models/de/css10/vits-neon
tts_models/ja/kokoro/tacotron2-DDC
tts_models/tr/common-voice/glow-tts
tts_models/it/mai_female/glow-tts
tts_models/it/mai_female/vits
tts_models/it/mai_male/glow-tts
tts_models/it/mai_male/vits
tts_models/ewe/openbible/vits
tts_models/hau/openbible/vits
tts_models/lin/openbible/vits
tts_models/tw_akuapem/openbible/vits
tts_models/tw_asante/openbible/vits
tts_models/yor/openbible/vits
tts_models/hu/css10/vits
tts_models/el/cv/vits
tts_models/fi/css10/vits
tts_models/hr/cv/vits
tts_models/lt/cv/vits
tts_models/lv/cv/vits
tts_models/mt/cv/vits
tts_models/pl/mai_female/vits
tts_models/pt/cv/vits
tts_models/ro/cv/vits
tts_models/sk/cv/vits
tts_models/sl/cv/vits
tts_models/sv/cv/vits
tts_models/ca/custom/vits
tts_models/fa/custom/glow-tts
tts_models/fa/custom/vits-female
tts_models/bn/custom/vits-male
tts_models/bn/custom/vits-female
tts_models/be/common-voice/glow-tts
vocoder_models/universal/libri-tts/wavegrad
vocoder_models/universal/libri-tts/fullband-melgan
vocoder_models/en/ek1/wavegrad
vocoder_models/en/librispeech100/wavlm-hifigan
vocoder_models/en/librispeech100/wavlm-hifigan_prematched
vocoder_models/en/ljspeech/multiband-melgan
vocoder_models/en/ljspeech/hifigan_v2
vocoder_models/en/ljspeech/univnet
vocoder_models/en/blizzard2013/hifigan_v2
vocoder_models/en/vctk/hifigan_v2
vocoder_models/en/sam/hifigan_v2
vocoder_models/nl/mai/parallel-wavegan
vocoder_models/de/thorsten/wavegrad
vocoder_models/de/thorsten/fullband-melgan
vocoder_models/de/thorsten/hifigan_v1
vocoder_models/ja/kokoro/hifigan_v1
vocoder_models/uk/mai/multiband-melgan
vocoder_models/tr/common-voice/hifigan
vocoder_models/be/common-voice/hifigan
voice_conversion_models/multilingual/vctk/freevc24
voice_conversion_models/multilingual/multi-dataset/knnvc
voice_conversion_models/multilingual/multi-dataset/openvoice_v1
voice_conversion_models/multilingual/multi-dataset/openvoice_v2
'''
def test_list_models():
  # List available 🐸TTS models
  for model in TTS().list_models():
      print(model)

def test_list_speakers():
  # Initialize TTS
  tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
  # List speakers
  for speaker in tts.speakers:
      print(speaker)
