# pyannote-audio in this project

## What is pyannote-audio?
pyannote-audio is a Python toolkit for speaker diarization and voice activity detection (VAD) built on PyTorch. It ships pretrained models and high-level pipelines (like VAD) that take audio and return speech segments.

## Why this project uses it
This repo uses pyannote-audio for background/silence detection via VAD:
- `lib/classes/background_detector.py` loads a pretrained segmentation model (`drewThomasson/segmentation`) and runs the `VoiceActivityDetection` pipeline.
- The result is used to compute a non-speech ratio and determine whether background audio is present.
In short, pyannote-audio provides ready-made VAD with good quality so the project can detect speech vs. non-speech reliably.

## Why it causes dependency management trouble
The pain points are typical for pyannote-audio and its stack:
- Heavy ML stack: it depends on PyTorch + torchaudio (large wheels, CUDA/CPU variants, strict version pinning).
- Tight version coupling: pyannote-audio, torchaudio, and torch often need matching versions; mismatches break installs.
- Transitive dependencies: pulls in `pyannote-core`, `pyannote-database`, `pyannote-metrics`, `pyannote-pipeline`, etc.
- Native/compiled deps: packages like `numba`/`llvmlite` and `torchcodec` can be fragile on Windows or with older Python.
- Model download requirement: `Model.from_pretrained` usually hits Hugging Face unless cached; offline mode complicates setup.

In this repo, those issues show up in `requirements.txt` and `run.cmd` where it installs `torch`, `torchaudio`, `pyannote.audio`, and also pins `numba==0.58.1` and `llvmlite==0.41.1` to keep the stack stable.

## Possible replacements (tradeoffs)
If you only need VAD for background detection, lighter-weight options exist:

1) WebRTC VAD (`webrtcvad` / `py-webrtcvad`)
   - Pros: tiny, fast, no heavy ML stack.
   - Cons: lower accuracy on noisy audio; needs framing and energy logic.

2) Silero VAD (`silero-vad`)
   - Pros: good accuracy, smaller and simpler than pyannote; runs on CPU.
   - Cons: still uses torch, but typically fewer deps and fewer version conflicts.

3) SpeechBrain VAD
   - Pros: good quality; already a dependency in some audio projects.
   - Cons: still heavyweight; similar torch stack issues.

4) Torchaudio VAD pipeline
   - Pros: already depends on torch/torchaudio; fewer extra packages than pyannote.
   - Cons: accuracy varies; APIs change across versions.

5) Simple energy-based VAD (librosa/ffmpeg)
   - Pros: no torch stack; very lightweight.
   - Cons: less robust on real-world noise; requires tuning.

## Suggested replacement path for this repo
If you want a lower-friction drop-in while keeping accuracy:
- Prefer Silero VAD as the first replacement candidate.
- Implement a small adapter class that returns speech segments and matches the current `detect()` interface.
- Keep the same `vad_ratio_thresh` logic so behavior stays consistent.

If you want the lightest possible dependency set:
- Use WebRTC VAD or an energy-based VAD and accept lower accuracy.

## Notes
This repo currently expects a pretrained model ID (`drewThomasson/segmentation`) and uses the pyannote pipeline directly, so any replacement should supply equivalent speech vs. non-speech segmentation.
