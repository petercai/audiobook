# XTTS vs CosyVoice fine-tuned 的差异与 speaker 影响

## XTTSv2 fine-tuned 仍需要 speaker_embedding
XTTSv2 的推理接口需要同时提供 gpt_cond_latent 和 speaker_embedding。即使模型是 fine-tuned（例如 drewThomasson/fineTunedTTSModels），模型参数只是把整体风格/发音习惯往训练说话人靠拢，但推理时依然要用 embedding 来确定具体说话人的音色。

如果提供另一位说话人的参考音频（如 Brina Palencia）：
- 输出音色会主要跟随该参考说话人。
- fine-tuned 权重会对韵律/口音/风格产生偏置，形成“模型偏好 + 参考音色”的组合效果。
- 这不是线性混音，而是条件控制 + 模型先验叠加。

## CosyVoice 的 fine-tuned（SFT）与 zero-shot 不同
在本项目代码里，CosyVoice 有两种路径：
- **CosyVoice-300M-SFT（fine-tuned/SFT）**：使用固定的 speaker id。不能直接用任意参考音频替换音色，只能在该模型支持的 speaker id 范围内切换。
- **CosyVoice2-0.5B（zero-shot）**：通过参考音频注册 speaker（dd_zero_shot_spk），之后用该 speaker id 推理。这个模式可以使用不同 speaker 的音频。

结论：CosyVoice 的 fine-tuned（SFT）和 XTTS 的 fine-tuned 机制不同；SFT 更像“固定说话人集合”，而 XTTS 仍依赖 embedding 做条件控制。

## 是否可以用不同 speaker 的 voice
- **CosyVoice SFT**：只能用模型内置的 speaker id，不支持任意参考音频。
- **CosyVoice zero-shot**：可以使用不同 speaker 的参考音频，但需要先注册。

## 对生成速度的影响
- **主要影响来自模型大小与设备**，而不是 speaker 本身。
- **XTTS**：首次使用某个参考音频会计算并缓存 embedding，第一次会慢一点；后续复用同一参考音频速度正常。
- **CosyVoice zero-shot**：注册新 speaker 时会有一次性开销；注册后推理速度主要由模型决定。
- **CosyVoice SFT**：不需要参考音频或 embedding，一般更稳定、开销更低。