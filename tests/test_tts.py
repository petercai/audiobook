import torch
from TTS.api import TTS

# Get device
device = "cuda" if torch.cuda.is_available() else "cpu"

# List available 🐸TTS models
print("default models:")
print(TTS().list_models())

# Initialize TTS
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

# List speakers
print
print(tts.speakers)


# List languages
print("languages:")
print(tts.languages)


# TTS to a file, use a preset speaker
tts.tts_to_file(
  text="The big ball of yellow might be spilling into the clouds, runny and yolky and blurring into the bluest sky, bright with cold hope and false promises about fond memories, real families, hearty breakfasts, stacks of pancakes drizzled in maple syrup sitting on a plate in a world that doesn’t exist anymore.",
  # speaker="Craig Gutsy",
  speaker_wav="voices/eng/adult/female/AlexandraHisakawa.wav",
  language="en",
  file_path="Alexandra.wav",
  split_sentences=True
)