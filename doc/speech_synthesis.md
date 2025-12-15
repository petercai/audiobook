# Speech Synthesis Flow (Coqui)

This document explains how `_load_checkpoint()` works in `lib/classes/tts_engines/coqui.py` and how speech is generated afterward. It focuses on XTTSv2 and Bark (the engines that use `_load_checkpoint`), and the common synthesis pipeline.

## Where the model lives after `_load_checkpoint()`
- `_load_checkpoint()` loads the model and moves it to the requested device (`cuda` or CPU).
- The loaded instance is cached in the global `loaded_tts` dictionary with the key passed in:
  - `loaded_tts[key]["engine"]` holds the model object (e.g., `Xtts`, `Bark`).
  - `loaded_tts[key]["config"]` stores the config used for Bark/XTTS.
- Because the object is cached, later code retrieves it from `loaded_tts[...]` and calls inference methods directly; no need to “find” files again with torch—weights are already in memory.

## `_load_checkpoint()` in detail
File: `lib/classes/tts_engines/coqui.py`, ~line 349.

1) Early exit if already cached  
   ```python
   if key in loaded_tts: return loaded_tts[key]["engine"]
   ```

2) Unload other models to free memory  
   ```python
   unload_tts(device, [self.tts_key, self.tts_vc_key])
   ```

3) Thread-safe load  
   Uses a `lock` to prevent concurrent loads.

4) Engine-specific load paths  
   - **XTTSv2**
     - Imports `XttsConfig`, `Xtts`.
     - Builds a config, sets `config.models_dir`.
     - `Xtts.init_from_config(config)` to create the model object.
     - `tts.load_checkpoint(config, checkpoint_path, vocab_path, use_deepspeed=..., eval=True)` loads weights.
   - **Bark**
     - Adds safe globals for torch serialization (numpy types).
     - Imports `BarkConfig`, `Bark`.
     - Sets cache/small-model flags in config.
     - `Bark.init_from_config(config)`, then `tts.load_checkpoint(config, checkpoint_dir=..., eval=True)`.

5) Move to device and cache  
   ```python
   tts.cuda() or tts.to(device)
   loaded_tts[key] = {"engine": tts, "config": config}
   ```

## How speech is generated after loading
Main entry: `convert()` (~line 540).

High-level steps:
1) Resolve voice path, speaker name, and optional conversions (XTTS built-ins; Bark NPZ generation).
2) Fetch the engine from `loaded_tts[self.tts_key]["engine"]`.
3) Handle special tokens (`<break>`, `<pause>`) by inserting silence tensors.
4) Engine-specific synthesis:
   - **XTTSv2**
     - Compute speaker latents: `tts.get_conditioning_latents(audio_path=[voice_path])` (or use built-in latents).
     - Build fine-tuning params from session (temperature, beams, etc.).
     - `tts.inference(text=..., language=..., gpt_cond_latent=..., speaker_embedding=..., **params)`.
     - Extract `result["wav"]`.
   - **Bark**
     - Ensure NPZ history prompt exists (may trigger internal Bark generation).
     - Load NPZ; build `history_prompt`.
     - `tts.generate_audio(sentence, history_prompt=..., silent=True, **params)`.
   - **VITS/FAIRSEQ/TACOTRON2**
     - `tts.tts_to_file(...)` to create an intermediate WAV, optional pitch shift (SoX), then voice conversion via `tts_vc.voice_conversion(...)` if a custom voice is used; otherwise `tts.tts(text=...)`.
   - **YourTTS**
     - `tts.tts(text=..., language=..., speaker_wav=... | speaker=...)`.

5) Post-processing
   - Convert numpy/list/tensor to torch tensor (`_tensor_type`).
   - Trim trailing silence (`trim_audio`).
   - Concatenate segments, maintain VTT timings, and save with `torchaudio.save(...)`.

## Torch functions commonly invoked
- Device placement: `tts.cuda()` or `tts.to(device)`
- No-grad for inference: `with torch.no_grad(): ...`
- Tensor conversion: `torch.tensor(...)`, `torch.from_numpy(...)`, cloning/detaching before CPU save.
- Audio save/load helpers: `torchaudio.save`, `torchaudio.load`, `torchaudio.transforms.Resample`
- XTTS latents: `tts.get_conditioning_latents(...)`
- XTTS inference: `tts.inference(...)`
- Bark generation: `tts.generate_audio(...)`
- VITS/FAIRSEQ/TACOTRON2 synthesis: `tts.tts_to_file(...)` (writes wav) or `tts.tts(...)`
- Voice conversion (if used): `tts_vc.voice_conversion(...)`

## Minimal end-to-end example (XTTSv2)
Pseudo-code using the existing class:

```python
from lib.classes.tts_engines.coqui import Coqui
session = {
    "tts_engine": "XTTSv2",
    "fine_tuned": "internal",
    "device": "cuda",
    "custom_model": None,
    "custom_model_dir": "/path/to/models",
    "language": "eng",           # full language key
    "language_iso1": "en",       # ISO-1 code used by XTTS
    "voice": "/path/to/ref.wav", # reference audio for cloning
    "process_dir": "/tmp/run",
    "final_name": "sample.wav",
    "chapters_dir_sentences": "/tmp/run/sentences",
    "voice_dir": "/tmp/run/voices",
    "offline_mode": False,
}

engine = Coqui(session)   # builds and caches model via _build/_load_checkpoint
engine.convert(1, "Hello world.")
```

- `Coqui(session)` calls `_build()`, which calls `_load_checkpoint(...)` for XTTSv2.
- The model is cached in `loaded_tts[...]` and on the chosen device.
- `convert()` performs inference and writes the sentence audio to `chapters_dir_sentences/1.wav` (default format).

## Key takeaways
- `_load_checkpoint()` loads weights into memory, moves the model to the target device, and caches it in `loaded_tts`.
- Subsequent synthesis uses the cached instance; torch does not re-read checkpoint files during inference.
- Core torch ops during synthesis: device placement, no-grad inference calls (`inference`, `tts`, `tts_to_file`, `generate_audio`, `voice_conversion`), tensor conversions, resampling, and final saving via `torchaudio`.
