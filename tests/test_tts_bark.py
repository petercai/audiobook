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
