import soundfile as sf
import numpy as np
from voxcpm import VoxCPM

model = VoxCPM.from_pretrained("openbmb/VoxCPM-0.5B")

# Non-streaming
wav = model.generate(
    text="The big ball of yellow might be spilling into the clouds, runny and yolky and blurring into the bluest sky, bright with cold hope and false promises about fond memories, real families, hearty breakfasts, stacks of pancakes drizzled in maple syrup sitting on a plate in a world that doesn’t exist anymore.",
    prompt_wav_path="voices/eng/adult/female/AlexandraHisakawa.wav",      # optional: path to a prompt speech for voice cloning
    prompt_text="Alexandra Hizakawa, an XTS Engine built-in voice, ready to speak for any kind of text. A big juicy fish jumps quickly, vexed, the dwarf whacks my zippered box.",          # optional: reference text
    cfg_value=2.0,             # LM guidance on LocDiT, higher for better adherence to the prompt, but maybe worse
    inference_timesteps=10,   # LocDiT inference timesteps, higher for better result, lower for fast speed
    normalize=True,           # enable external TN tool
    denoise=True,             # enable external Denoise tool
    retry_badcase=True,        # enable retrying mode for some bad cases (unstoppable)
    retry_badcase_max_times=3,  # maximum retrying times
    retry_badcase_ratio_threshold=6.0, # maximum length restriction for bad case detection (simple but effective), it could be adjusted for slow pace speech
)

sf.write("output.wav", wav, 16000)
print("saved: output.wav")

# Streaming
# chunks = []
# for chunk in model.generate_streaming(
#     text = "Streaming text to speech is easy with VoxCPM!",
#     # supports same args as above
# ):
#     chunks.append(chunk)
# wav = np.concatenate(chunks)

# sf.write("output_streaming.wav", wav, 16000)
# print("saved: output_streaming.wav")