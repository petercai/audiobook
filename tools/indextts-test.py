from indextts.infer_v2 import IndexTTS2

if __name__ == "__main__":
    prompt_wav="voices/zho/adult/male/yunyang.wav"
    tts = IndexTTS2(cfg_path="models/tts/config.yaml", model_dir="models/tts", use_fp16=True, use_cuda_kernel=False, offline_mode=True)    
    text="亲爱的伙伴们，大家好！每一次的努力都是为了更好的未来，要善于从失败中汲取经验，让我们一起勇敢前行,迈向更加美好的明天！"
    tts.infer(spk_audio_prompt=prompt_wav, text=text, output_path=f"outputs/{text[:20]}.wav")
