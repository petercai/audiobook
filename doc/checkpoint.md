# checkpoint 说明

## checkpoint 是什么
- 训练过程中模型状态的快照，通常以 .pth/.pt/.ckpt 保存权重，可能包含训练步数、优化器等上下文，用于继续训练或推理。
- 不一定自带模型结构定义，恢复时需要配套的配置文件来重建模型。

## 和 “model 文件” 的区别
- “model 文件”常指已经打包好的推理产物（有时是 ONNX/量化/单文件封装），拿到即可推理，基本不需要额外的配置。
- checkpoint 更像原始训练快照，依赖外部的 config/tokenizer/附加资源来构建模型，通常更灵活但耦合度更高。
- 本项目里的 XTTSv2、Bark 都采用“checkpoint + 配置 + 词表”的方式，不是单一自包含的模型包。

## 加载 checkpoint 需要哪些信息
- 权重文件本身：例如 model.pth、text_2.pt、coarse_2.pt、fine_2.pt。
- 架构/超参：config.json（层数、维度、音频参数、采样率等）。
- 词表/分词器：vocab.json 或 tokenizer_file，用于把文本编码成模型输入。
- 附加资源（因模型而异）：XTTSv2 的 speakers_xtts.pth，Bark 的 hubert tokenizer；通常与权重放在同目录或由库自动下载。
- 运行参数：device（cpu/cuda）、use_deepspeed、eval 模式开关等。

## 本项目的 checkpoint 需求
- 关键逻辑：`lib/classes/tts_engines/coqui.py:97-210`（选择模型、下载/定位文件）和 `lib/classes/tts_engines/coqui.py:312-398`（具体 load_checkpoint）。
- 文件清单定义：`lib/models.py:42-159` 的 `default_engine_settings`。

### XTTSv2
- 需要文件：config.json、model.pth、vocab.json，选配 speakers_xtts.pth（内置说话人列表）和 ref.wav（参考示例）。文件名列在 `default_engine_settings['xtts']['files']`（`lib/models.py:42-59`）。
- 加载流程（`lib/classes/tts_engines/coqui.py:129-181` & `312-369`）：
  1) `XttsConfig` 读取 config.json，设置 `models_dir`。
  2) `Xtts.init_from_config(config)` 构建模型。
  3) `tts.load_checkpoint(config, checkpoint_path=..., vocab_path=..., use_deepspeed=?, eval=True)` 加载权重与 tokenizer。
  4) 将模型移到 device 并缓存。
- 直接调用示例：
```python
from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import Xtts
config = XttsConfig(); config.load_json("config.json")
model = Xtts.init_from_config(config)
model.load_checkpoint(config, checkpoint_path="model.pth", vocab_path="vocab.json", eval=True)
```

### Bark
- 需要文件：checkpoint_dir 下的 text_2.pt、coarse_2.pt、fine_2.pt（`lib/models.py:83-88`），hubert tokenizer 由库自动处理/下载。
- 加载流程（`lib/classes/tts_engines/coqui.py:165-181` & `370-398`）：
  1) `BarkConfig` 设置 `CACHE_DIR`、`USE_SMALLER_MODELS`。
  2) `Bark.init_from_config(config)` 构建模型。
  3) `tts.load_checkpoint(config, checkpoint_dir=..., eval=True)` 读取目录中的权重。
  4) 移到 device。
- 示例：
```python
from TTS.tts.configs.bark_config import BarkConfig
from TTS.tts.models.bark import Bark
config = BarkConfig()
model = Bark.init_from_config(config)
model.load_checkpoint(config, checkpoint_dir="path/to/bark_dir", eval=True)
```

### 其他 TTS 引擎简述
- VITS / FAIRSEQ / TACOTRON2 / YOURTTS 也是“config.json + *.pth (+ tokenizer 等)”的组合，文件名可在 `default_engine_settings[...]` 中查看。
- 通过 `_load_api` 拉取的模型通常已由 Hugging Face 打包，checkpoint 细节由上游库处理。

## 小结
- checkpoint = 训练权重快照，加载时需配套 config、词表和特定附加资源；“model 文件”更像可直接推理的封装产物。
- 在本仓库使用 XTTSv2/Bark 时，请确保配置、权重、词表/分词器、可选 speakers 文件都在可访问路径（离线模式需提前放入缓存目录）。
