# 说话人处理与 `_check_xtts_builtin_speakers()` 行为说明

## 为什么需要 `_check_xtts_builtin_speakers()`
- 触发条件：`convert()` 里如果当前语言不是 `eng`，`voice_path` 仍指向英语内置音色（路径里没有目标语言目录），且说话人名不在 Bark 内置列表，就会调用该函数（`lib/classes/tts_engines/coqui.py:461`）。
- 作用：把英语内置音色的参考片段转换成目标语言的片段，路径也替换为 `voices/<目标语言>/...`。这样在克隆非英语时不会一直引用英语样本，避免口音/韵律错配，同时为后续复用留下本地缓存。
- 实现步骤：加载 XTTSv2 内置模型 → 读取目标语言 `default.txt` → 取对应说话人的潜变量（内置音色直接从 `speakers_xtts.pth` 读取，非内置则实时算）→ 用目标语言推理出一小段语音 → 归一化后写入新路径；如果当前主引擎不是 XTTSv2，会在结束后卸载这个临时加载的 XTTS 模型释放显存。

## 为什么总要拉取 XTTSv2 的 `config.json`、`model.pth`、`vocab.json`
- XTTSv2 在 `_handle_xttsv2()` 和 `_check_xtts_builtin_speakers()` 里都需要完整的模型三件套：`config.json` 描述网络与超参、`model.pth` 是权重、`vocab.json` 是分词表。缺任何一个都无法实例化 `Xtts` 或完成推理。
- 即便主 TTS 引擎不是 XTTSv2，只要触发了上面的“英语内置音色 → 非英语”转换，就必须先把这三个文件下载到缓存（`hf_hub_download`），才能用 XTTS 生成那段目标语言的参考音频。
- 另外会额外加载 `speakers_xtts.pth`（含预计算的潜变量）以快速获得内置说话人的 `gpt_cond_latent` 和 `speaker_embedding`，避免每次都重新提取。

## 使用 Bark 时是否需要这些文件
- 如果你选的是 Bark 内置说话人（`de_speaker_0` 等）或提供了自备提示音频，`_check_xtts_builtin_speakers()` 不会触发，Bark 只会用自己的模型文件和 `_check_bark_npz()` 来生成/检查 `*.npz` 提示，不需要 XTTS 的 `config/model/vocab`。
- 只有当“目标语言 ≠ 英语”且你提供的参考语音是 XTTS 内置英语音色时，即便当前主引擎是 Bark，也会临时拉起 XTTSv2 生成一段目标语言参考音频，因此会看到下载这三个文件的行为。
