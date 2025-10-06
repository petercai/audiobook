import soundfile as sf
import numpy as np
from voxcpm import VoxCPM

model = VoxCPM.from_pretrained("openbmb/VoxCPM-0.5B")

# Non-streaming
wav = model.generate(
    text="二愣子睁大着双眼，直直望着茅草和烂泥糊成的黑屋顶，身上盖着的旧棉被，已呈深黄色，看不出原来的本来面目，还若有若无的散发着淡淡的霉味。",
    prompt_wav_path="voices/zho/adult/male/yunjian_24000.wav",      # optional: path to a prompt speech for voice cloning
    prompt_text="无论是互联网巨头还是刚起步的创业公司都在竞相努力成为元宇宙这条充满无限可能性赛道的领先者事实确实这些平台除了产品发布发新闻稿时热度高很快就回归平静就像horizon world一样",          # optional: reference text
    cfg_value=2.0,             # LM guidance on LocDiT, higher for better adherence to the prompt, but maybe worse
    inference_timesteps=10,   # LocDiT inference timesteps, higher for better result, lower for fast speed
    normalize=True,           # enable external TN tool
    denoise=True,             # enable external Denoise tool
    retry_badcase=True,        # enable retrying mode for some bad cases (unstoppable)
    retry_badcase_max_times=3,  # maximum retrying times
    retry_badcase_ratio_threshold=6.0, # maximum length restriction for bad case detection (simple but effective), it could be adjusted for slow pace speech
)

sf.write("god-1.wav", wav, 16000)
print("saved: god-1.wav")

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