Here is a sample Python script that uses Coqui-TTS’s Bark model + a reference Chinese speaker WAV (e.g. `yunjian.wav`) to convert a Chinese text file into speech with voice cloning. You’ll likely need to tweak hyperparameters and ensure model files are properly downloaded / paths set.

Note: The Coqui TTS Bark integration supports passing a `speaker_wav` reference for voice cloning. ([coqui-tts.readthedocs.io][1])

```python
import os
import torch
from TTS.tts.configs.bark_config import BarkConfig
from TTS.tts.models.bark import Bark
from TTS.utils.audio import AudioProcessor

def load_text_file(txt_path: str, encoding: str = "utf-8") -> str:
    with open(txt_path, "r", encoding=encoding) as f:
        return f.read()

def text_to_speech_bark(
    text: str,
    speaker_wav: str,
    out_wav: str,
    device: str = "cuda" if torch.cuda.is_available() else "cpu",
    # you can pass additional Bark-specific kwargs here:
    **bark_kwargs
):
    # load model config and model
    config = BarkConfig()
    model = Bark.init_from_config(config)
    # you need to load pretrained checkpoints (text, coarse, fine, hubert tokenizer)
    # e.g. if your bark model files are under “bark_checkpoint_dir/”
    bark_checkpoint_dir = bark_kwargs.get("checkpoint_dir", "bark_model")
    model.load_checkpoint(
        config,
        checkpoint_dir=bark_checkpoint_dir,
        eval=True
    )
    model = model.to(device)
    model.eval()

    # synthesize with voice cloning reference
    out = model.synthesize(
        text,
        config,
        speaker_wav=speaker_wav,
        **bark_kwargs
    )
    wav = out["wav"]  # a torch.Tensor, shape (samples,)
    # Convert to numpy and save via AudioProcessor
    ap = AudioProcessor.init_from_config(config)
    ap.save_wav(wav.cpu().numpy(), out_wav)
    print(f"Saved to {out_wav}")

def main():
    # paths
    txt_path = "input_chinese.txt"
    speaker_wav = "yunjian.wav"
    output_wav = "output.wav"

    text = load_text_file(txt_path)
    # optional: you may want to chunk the text into sentences for better results,
    # especially for very long text.

    text_to_speech_bark(
        text,
        speaker_wav=speaker_wav,
        out_wav=output_wav,
        checkpoint_dir="path/to/bark_checkpoint_dir",
        # you can pass other gen params like top_k, top_p, temp etc
        top_k=50,
        top_p=0.95,
        temp=0.7,
    )

if __name__ == "__main__":
    main()
```

### Notes / caveats / tips & improvements

* The `synthesize` method in Bark supports a `speaker_wav` parameter for reference audio (your `yunjian.wav`). ([coqui-tts.readthedocs.io][1])
* The model must be loaded with the correct checkpoint files (text, coarse, fine, hubert tokenizer) in the directory you pass. ([coqui-tts.readthedocs.io][1])
* For Chinese text, ensure your text file is encoded properly (UTF-8) and perhaps segmented (sentence/phrase boundaries) so that Bark doesn’t try to generate excessively long speech at once.
* You may need to adjust generation parameters (top_k, top_p, temperature) to get more stable / high quality audio.
* If memory is limited, you may need to split long text into segments, generate separately, then concatenate WAVs.
* Always run `.eval()` on the model and move it to GPU (if available) for faster / better inference.
* Because Bark is a relatively newer model integration, you may run into dependency or path issues. Check the Coqui-TTS docs and Bark config integration (e.g. `tts_models/bark` in the model list) for correct config paths. ([docs.coqui.ai][2])

If you like, I can also help you with a fuller working example (with downloading the model, chunking text, error handling) tailored to your environment (CPU, GPU, etc.). Do you want me to provide that?

[1]: https://coqui-tts.readthedocs.io/en/latest/_modules/TTS/tts/models/bark.html?utm_source=chatgpt.com "TTS.tts.models.bark - coqui-tts 0.26.1 documentation"
[2]: https://docs.coqui.ai/en/latest/models/bark.html?utm_source=chatgpt.com "Bark - TTS 0.22.0 documentation"
