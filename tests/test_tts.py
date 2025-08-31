import torch
from TTS.api import TTS

# Get device
device = "cuda" if torch.cuda.is_available() else "cpu"

# List available 🐸TTS models
# print(TTS().list_models())

# Initialize TTS
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

# List speakers
print(tts.speakers)

# Run TTS
# ❗ XTTS supports both, but many models allow only one of the `speaker` and
# `speaker_wav` arguments

# TTS with list of amplitude values as output, clone the voice from `speaker_wav`
# wav = tts.tts(
#   text="The big ball of yellow might be spilling into the clouds, runny and yolky and blurring into the bluest sky, bright with cold hope and false promises about fond memories, real families, hearty breakfasts, stacks of pancakes drizzled in maple syrup sitting on a plate in a world that doesn’t exist anymore.",
#   speaker_wav="voices/eng/adult/female/AlexandraHisakawa_16000.wav",
#   language="en"
# )




# TTS to a file, use a preset speaker
tts.tts_to_file(
  text="The big ball of yellow might be spilling into the clouds, runny and yolky and blurring into the bluest sky, bright with cold hope and false promises about fond memories, real families, hearty breakfasts, stacks of pancakes drizzled in maple syrup sitting on a plate in a world that doesn’t exist anymore.",
  # speaker="Craig Gutsy",
  speaker_wav="voices/eng/adult/female/AlexandraHisakawa_16000.wav",
  language="en",
  file_path="Alexandra.wav",
  split_sentences=True
)