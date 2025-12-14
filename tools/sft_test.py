import os
# from pathlib import Path
import torch
import torchaudio
from cosyvoice.cli.cosyvoice import CosyVoice
from lib.conf import tts_dir

model_dir = os.path.join(tts_dir, "CosyVoice-300M-SFT")

cosyvoice = CosyVoice(model_dir, load_jit=False, load_trt=False, fp16=False)
spk_ids = ['中文女', '中文男', '粤语女']

tts_text = '收到好友从远方寄来的生日礼物，那份意外的惊喜与深深的祝福让我心中充满了甜蜜的快乐，笑容如花儿般绽放。'
# spk_ids = cosyvoice.list_available_spks()
# print('available spk_id:', spk_ids)

for spk_id in spk_ids:
    chunks = []
    for out in cosyvoice.inference_sft(tts_text, spk_id, stream=False):
        chunks.append(out['tts_speech'])
    if len(chunks) == 0:
        continue
    speech = torch.cat(chunks, dim=1)
    filename = f'sft_{spk_id}.wav'
    torchaudio.save(filename, speech, cosyvoice.sample_rate)
    print('saved', filename)
