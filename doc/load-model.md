# load-model 说明

## `_load_api()` 做什么
- 位置：`lib/classes/tts_engines/coqui.py:253-310`。
- 用途：调用 Coqui `TTS.api.TTS(model_path)` 按模型名/路径直接加载已打包的推理模型（自动处理依赖与下载）。
- 步骤：
  1) 先查全局缓存 `loaded_tts`，命中则复用。
  2) 调 `unload_tts()` 释放其他模型（节省显存/内存）。
  3) 线程锁内实例化 `TTS(model_path)`。
  4) 挂载到 device（cuda/cpu），写入缓存。
- 适用：VITS、FAIRSEQ、TACOTRON2、YOURTTS，以及零样本 VC 模型（如 `default_vc_model`）。这些模型在 Coqui 模型库中已有可直接加载的打包版本。

## `_load_checkpoint()` 与 `_load_api()` 的区别
- `_load_checkpoint()`：手动组装模型，再用 `load_checkpoint(...)` 喂入权重/词表；需要显式提供 `config_path`、`checkpoint_path`/`checkpoint_dir`、`vocab_path` 等。用于多文件、未完全打包的模型。
- `_load_api()`：调用封装好的 `TTS(model_path)` 一步到位，配置/权重路径由上游模型包给出，无需手动拼装。

## 为什么 XTTSv2 和 Bark 用 `_load_checkpoint()`
- XTTSv2（`coqui.py:129-181, 312-369`）：
  - 需要 `config.json + model.pth + vocab.json`（`lib/models.py:42-59`），可选 `speakers_xtts.pth`、`ref.wav`。
  - 需先 `XttsConfig.load_json(...)`，再 `Xtts.init_from_config(config)`，最后 `tts.load_checkpoint(..., use_deepspeed=..., eval=True)`。
  - 额外控制：`models_dir`、deepspeed 开关、device 迁移、缓存。
- Bark（`coqui.py:165-181, 370-398`）：
  - 依赖 checkpoint 目录下的 `text_2.pt/coarse_2.pt/fine_2.pt`（`lib/models.py:83-88`），Hubert tokenizer 由库自动处理。
  - 需显式创建 `BarkConfig`（设置 `CACHE_DIR`、`USE_SMALLER_MODELS`），再 `Bark.init_from_config(config)`，最后 `tts.load_checkpoint(config, checkpoint_dir=..., eval=True)`。
- 这两类模型当前并未以单文件/单标识打包到 `TTS.api` 的可直接加载范式中，需要手动传入配置与权重。

## 为什么 VITS / FAIRSEQ / TACOTRON2 / YOURTTS 用 `_load_api()`
- 这些模型在 Coqui 发布的推理入口里已有“可直接加载”的模型标识（或 HF 路径），`TTS(model_path)` 会自动解析内部的 config、vocab、权重位置并完成初始化。
- 项目中只需提供模型名/路径（通过 `models[...]`/`language_tts[...]` 计算），不必关心具体文件名，维护成本低。

## 快速对照表
- XTTSv2、Bark：需要手动配置 + `load_checkpoint`，走 `_load_checkpoint()`。
- VITS、FAIRSEQ、TACOTRON2、YOURTTS、VC 模型：已打包，可直接 `TTS(model_path)`，走 `_load_api()`。

## 小提示
- 离线模式下（`session['offline_mode']=True`），必须提前把所需文件放进缓存目录，`hf_hub_download(..., local_files_only=True)` 才能命中。
- 无论哪种加载方式，函数都会在加载后把模型移到指定 device 并写入 `loaded_tts` 缓存，以避免重复下载/初始化。

## 新模型如何判断使用 `_load_api` 还是 `_load_checkpoint`
- 先看发布形态：
  - 如果官方给出可直接 `TTS("repo_or_name")` 的标识（通常在 Coqui 公告或 HF `tts_models/...` 前缀），优先用 `_load_api`。
  - 如果提供的是散装文件（config.json + *.pth/pt + 词表等），且需要你手动拼路径，则用 `_load_checkpoint`。
- 参考现有定义：`lib/models.py` 里已有的 `files` 列表往往意味着需要 `_load_checkpoint`；空列表或只给模型名/路径的，更可能走 `_load_api`。
- 试探加载：
  - `_load_api` 失败但文件齐全 → 改用 `_load_checkpoint`。
  - `_load_checkpoint` 缺配置/词表且官方说明支持 API → 改用 `_load_api`。

### 针对 voxcpm / indextts / cosyvoice 的建议
- voxcpm、indextts：若上游提供 `TTS("voxcpm" 或 HF 路径)` 的直接入口，先尝试 `_load_api`；若只给出 config + 权重 + tokenizer，改用 `_load_checkpoint` 并在 `default_engine_settings` 补充文件名列表。
- cosyvoice：通常发布为多文件 checkpoint（config + 模型权重 + tokenizer + 声码器），倾向 `_load_checkpoint`；若后续 Coqui 官方提供了 API 模型名，再切到 `_load_api`。

### 实操检查清单
1) 查看模型文档是否有 `TTS("model_id")` 示例；有则 `_load_api`。
2) 查看发布包：是否有 config.json / vocab.json / *.pth 多文件？有则 `_load_checkpoint`。
3) 评估依赖：需要自定义分词器、声码器、特定环境变量时，更适合 `_load_checkpoint`。
4) 离线/本地文件场景：你已手动下载所有文件时，`_load_checkpoint` 更可控；在线自动下载更适合 `_load_api`。
