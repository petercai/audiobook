# `_load_checkpoint()` 与语音合成流程（Coqui）

本文介绍 `lib/classes/tts_engines/coqui.py` 里 `_load_checkpoint()` 的执行细节，以及模型加载完成后语音合成是如何调用 Torch 完成的。重点覆盖需要手动装载 checkpoint 的 XTTSv2 与 Bark。

## 模型加载后放在哪里？
- `_load_checkpoint()` 会把模型权重加载进内存，并移动到指定设备（`cuda` 或 `cpu`）。
- 模型实例被放入全局缓存 `loaded_tts`，键由调用方传入：
  - `loaded_tts[key]["engine"]` 存放模型对象（`Xtts` 或 `Bark`）。
  - `loaded_tts[key]["config"]` 保存对应配置（Bark/XTTS 用）。
- 之后推理阶段直接从 `loaded_tts[...]` 取实例；Torch 不再重复读取 checkpoint 文件，权重已在内存和目标设备上。

## `_load_checkpoint()` 执行过程
位置：`lib/classes/tts_engines/coqui.py`。

1) 缓存短路  
```python
if key in loaded_tts: return loaded_tts[key]["engine"]
```

2) 释放旧模型  
```python
unload_tts(device, [self.tts_key, self.tts_vc_key])
```

3) 加载加锁  
使用全局 `lock`，避免多线程同时加载。

4) 按引擎类型分别加载  
- **XTTSv2**
  - 导入 `XttsConfig`, `Xtts`。
  - `config = XttsConfig(); config.models_dir = "models/tts"; config.load_json(config_path)`。
  - `tts = Xtts.init_from_config(config)` 建立骨架。
  - `tts.load_checkpoint(config, checkpoint_path=..., vocab_path=..., use_deepspeed=..., eval=True)` 喂入权重与词表。
- **Bark**
  - 为反序列化添加 numpy 安全类型：`torch.serialization.add_safe_globals([...])`。
  - `config = BarkConfig(); config.CACHE_DIR = cache_dir; config.USE_SMALLER_MODELS = env_flag`。
  - `tts = Bark.init_from_config(config)` 后 `tts.load_checkpoint(config, checkpoint_dir=..., eval=True)`。

5) 放到设备并缓存  
```python
tts.cuda() 或 tts.to(device)
loaded_tts[key] = {"engine": tts, "config": config}
```
此后模型常驻缓存，后续推理直接取用。

## 语音生成整体流程
入口：`convert()`（同文件）。

1) 准备语音参考  
解析 `session` 里 voice 路径/说话人名；如是 XTTS 内置英文音色且目标语言非英语，会先调用 `_check_xtts_builtin_speakers()` 生成目标语言语音样本；Bark 则确保对应 `*.npz` 提示存在。

2) 取出已缓存的模型  
`tts = loaded_tts[self.tts_key]["engine"]`。

3) 特殊标记处理  
遇到 `<break>`/`<pause>` 时，直接拼接静音张量返回。

4) 按引擎推理  
- **XTTSv2**：先算或读取说话人潜变量  
  - 若是内置音色：直接从 `xtts_builtin_speakers_list` 取 `gpt_cond_latent` 与 `speaker_embedding`。  
  - 非内置：`tts.get_conditioning_latents(audio_path=[voice_path])`。  
  - 拼接采样超参（温度、beam、top_k/top_p 等），`tts.inference(text=..., language=..., gpt_cond_latent=..., speaker_embedding=..., **params)`；结果字段 `result["wav"]`。
- **Bark**：准备 history prompt（来自 `npz` 的 semantic/coarse/fine 三段）；`tts.generate_audio(sentence, history_prompt=..., silent=True, **params)`。
- **VITS/FAIRSEQ/TACOTRON2**：`tts.tts_to_file(...)` 先产出中间 WAV，按性别差异可用 SoX 变调，再用声纹转换模型 `tts_vc.voice_conversion(source_wav=..., target_wav=...)`；若无自定义音色则直接 `tts.tts(text=...)`。
- **YourTTS**：`tts.tts(text=..., language=..., speaker_wav=... | speaker=...)`。

5) 后处理与落盘  
- 将 `list/numpy/tensor` 转成 torch 张量 `_tensor_type()`；必要时用 `trim_audio` 去尾静音。  
- 在需要的地方追加短静音分隔，累计到 `audio_segments`。  
- 拼接整句张量，计算时间轴写入 VTT（`append_sentence2vtt`），再用 `torchaudio.save(...)` 保存到 `chapters_dir_sentences/{n}.wav`。

## 合成过程中用到的 Torch 调用
- 设备放置：`tts.cuda()` / `tts.to(device)`。
- 推理免梯度：`with torch.no_grad(): ...`。
- 条件向量/说话人嵌入：`tts.get_conditioning_latents(...)`（XTTS）。
- 主推理：`tts.inference(...)`（XTTS）、`tts.generate_audio(...)`（Bark）、`tts.tts_to_file(...)` 与 `tts.tts(...)`（VITS/FAIRSEQ/TACOTRON2）、`tts_vc.voice_conversion(...)`（声纹转换）。
- 张量与音频 I/O：`torch.tensor/torch.from_numpy/clone/detach`，`torchaudio.load`、`torchaudio.save`、`torchaudio.transforms.Resample`。

### 关键调用详解
- **推理免梯度：`with torch.no_grad(): ...`**  
  关闭梯度计算的上下文管理器。推理阶段不需要反向传播，关闭梯度可以：1）减少显存/内存占用；2）避免无用的计算图构建；3）提高推理速度。在 `convert()` 里，XTTS、Bark 等推理都包在 `torch.no_grad()` 中。

- **条件向量/说话人嵌入：`tts.get_conditioning_latents(audio_path=[...])`（XTTS）**  
  给模型一段参考语音（wav），返回两类潜变量：`gpt_cond_latent`（文本生成条件）和 `speaker_embedding`（说话人特征）。后续 `tts.inference(...)` 需要这两个向量来实现声音克隆。内置音色会直接复用预存好的潜变量，省去计算。

- **张量与音频 I/O**  
  - `torch.tensor(...)` / `torch.from_numpy(...)`：把 Python list 或 NumPy 数组转成 Torch 张量，便于后续张量运算或保存。  
  - `.clone().detach()`：复制张量并切断梯度/计算图，确保保存或拼接时不携带 autograd 信息。  
  - `torchaudio.load(path)`：读取音频文件，返回 `(waveform, sample_rate)`，waveform 是形如 `(channels, time)` 的张量。  
  - `torchaudio.save(path, waveform, sample_rate, format=...)`：把张量写成音频文件。`convert()` 里最终把合成后的张量保存为 wav。  
  - `torchaudio.transforms.Resample(orig_freq, new_freq)`：重采样工具，把音频从原采样率转换到目标采样率，用于声纹转换等场景保证模型期望的采样率。

## 简单示例：XTTSv2 端到端
```python
from lib.classes.tts_engines.coqui import Coqui

session = {
    "tts_engine": "XTTSv2",
    "fine_tuned": "internal",
    "device": "cuda",          # 或 "cpu"
    "custom_model": None,
    "custom_model_dir": "/path/to/models",
    "language": "eng",         # 内部语言键
    "language_iso1": "en",     # XTTS 用的 ISO-1
    "voice": "/path/to/ref.wav",
    "process_dir": "/tmp/run",
    "final_name": "sample.wav",
    "chapters_dir_sentences": "/tmp/run/sentences",
    "voice_dir": "/tmp/run/voices",
    "offline_mode": False,
}

engine = Coqui(session)      # _build() 内部会调用 _load_checkpoint() 装载 XTTSv2
engine.convert(1, "Hello world.")
```
- `_build()` 通过 `_load_checkpoint()` 把 XTTSv2 权重加载到 `loaded_tts[...]` 并移动到指定设备。
- `convert()` 直接复用缓存模型推理，并把音频写到 `chapters_dir_sentences/1.wav`。
