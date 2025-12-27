"""
Utility script to append a file from the Hugging Face Hub model
`drewThomasson/fineTunedTTSModels` to a local file.
"""


from huggingface_hub import snapshot_download

import os

models_dir = os.path.abspath('models')
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

# SDK模型下载
from modelscope import snapshot_download
snapshot_download('iic/CosyVoice2-0.5B', local_dir='models/tts/CosyVoice2-0.5B')
# snapshot_download('iic/CosyVoice-ttsfrd', local_dir='models/tts/CosyVoice-ttsfrd')