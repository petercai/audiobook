python app.py
python app.py --offline_mode

pip install -r requirements.txt --proxy http://webproxy.bns:8080 --trusted-host pypi.org --trusted-host files.pythonhosted.org
pip install -r requirements.txt --proxy http://localhost:9000 --trusted-host pypi.org --trusted-host files.pythonhosted.org

python app.py --headless --ebook ebooks/god-c1.txt --language zh-cn --voice zho/adult/male/yunxi_24000.wav 
python app.py --headless --ebook ebooks/god-c12.epub --language zh-cn --voice zho/adult/male/yunxi_24000.wav 


python app.py --headless --ebook ebooks/god-c1.txt --language zho --voice voices/zho/adult/male/yunxi_24000.wav

python app.py --headless --ebook ebooks/god-1.txt --device mps --tts_engine xtts --language zho --voice voices/zho/adult/male/yunxi_24000.wav --output_dir tmp 
python app.py --headless --ebook ebooks/god-1.txt --device mps --tts_engine bark --language zho --voice voices/zho/adult/male/yunxi_24000.wav --output_dir tmp

python app.py --headless --ebook ebooks/UnravelMe_one_sentense.txt --device gpu --tts_engine xtts
python app.py --headless --ebook ebooks/god-1.txt --device gpu --tts_engine xtts --language zho --voice voices/zho/adult/male/yunxi_24000.wav 
python app.py --headless --ebook ebooks/god-1.txt --device gpu --tts_engine bark --language zho --voice voices/zho/adult/male/yunxi_24000.wav 
python app.py --headless --ebook ebooks/god-1.txt --device gpu --tts_engine voxcpm --language zho --voice voices/zho/adult/male/yunxi_24000.wav 


uv add torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu129
uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu129


# For CUDA 12.8
uv pip install --no-cache-dir torch==2.7.0 torchvision==0.22.0 torchaudio==2.7.0 --index-url https://download.pytorch.org/whl/cu128

# For CUDA 11.8
pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# For CUDA 12.1
pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

pipdeptree > deps.txt
uv pip list --outdated > outdated.txt
uv pip list > list.txt

uv pip install -U  coqui-tts torch torchaudio torchvision pyannote.audio pyannote-audio transformers speechbrain torchcodec numba==0.58.1 llvmlite==0.41.1
uv pip show coqui-tts torch torchaudio torchvision pyannote.audio transformers speechbrain
uv pip install -U gradio

uv pip install numba==0.58.1 llvmlite==0.41.1
uv pip install gradio==5.42.0
uv pip install protobuf==3.20.3
uv pip install "gradio==5.42.0"
uv pip install "torch==2.8.*" "torchaudio==2.8.*"
uv pip install stanza==1.11.0
uv pip install "wetext>=0.1.2"

uv pip install  --no-deps  textsplit
uv pip install  --no-deps  spacy
uv pip install  --no-deps  snownlp
uv pip install  --no-deps  pyhanlp
uv pip install  --no-deps pysbd

uv pip install --no-deps matcha-tts

# From a local directory
uv pip install --no-deps -e /path/to/matcha-tts
# Or directly from Git
uv pip install --no-deps git+https://github.com/<org>/matcha-tts.git

# mac
uv pip install -e ../tts/CosyVoice
# linux
uv pip install --no-deps -e ../cosyvoice
# win
uv pip install --no-deps -e ../CosyVoice/
uv pip install --no-deps -e ../CosyVoice/third_party/Matcha-TTS


cd models/tts/CosyVoice-ttsfrd/
unzip resource.zip -d .
uv pip install ttsfrd_dependency-0.1-py3-none-any.whl
uv pip install ttsfrd-0.4.2-cp310-cp310-linux_x86_64.whl

## Linux

# folder storage usage
du -h --max-depth=1 | sort -hr

# disk usage
df -h

@REM Also check mounted volumes:
lsblk

pytest tests/test_epub.py::test_filter_chapter
pytest tests/test_epub.py::test_process_epub_chapters_en
pytest tests/test_epub.py::test_process_epub_chapters_zh
pytest tests/test_text_normalizer.py::test_normalize_text_4_tts_chinese
pytest tests/test_text_normalizer.py