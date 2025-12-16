"""
Utility script to append a file from the Hugging Face Hub model
`drewThomasson/fineTunedTTSModels` to a local file.
"""


from huggingface_hub import snapshot_download

import os

models_dir = '''e:\huggingface\hub'''
tts_dir = os.path.join(models_dir, 'tts')

# os.environ['PYTHONWARNINGS'] = 'ignore::UserWarning:torchaudio'
os.environ['PYTHONUTF8'] = '1'
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['COQUI_TOS_AGREED'] = '1'
os.environ['CALIBRE_NO_NATIVE_FILEDIALOGS'] = '1'
os.environ['GRADIO_DEBUG'] = '1'
os.environ['DO_NOT_TRACK'] = 'true'
os.environ['HUGGINGFACE_HUB_CACHE'] = tts_dir
os.environ['HF_HOME'] = tts_dir
os.environ['HF_DATASETS_CACHE'] = tts_dir
os.environ['BARK_CACHE_DIR'] = tts_dir
os.environ['TTS_CACHE'] = tts_dir
os.environ['TORCH_HOME'] = tts_dir
os.environ['TTS_HOME'] = models_dir
os.environ['XDG_CACHE_HOME'] = models_dir


REPO_ID = "drewThomasson/fineTunedTTSModels"
print(f"cache dir {tts_dir}")
downloaded_path = snapshot_download(
    repo_id=REPO_ID,
    cache_dir=tts_dir,
    local_files_only=False,
)

print(f"Downloaded '{downloaded_path}'.")


