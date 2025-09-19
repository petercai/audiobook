python app.py

pip install -r requirements.txt --proxy http://webproxy.bns:8080 --trusted-host pypi.org --trusted-host files.pythonhosted.org
pip install -r requirements.txt --proxy http://localhost:9000 --trusted-host pypi.org --trusted-host files.pythonhosted.org

python app.py --headless --ebook ebooks/god-c1.txt --language zh-cn --voice zho/adult/male/yunxi_24000.wav --output_dir tmp
python app.py --headless --ebook ebooks/god-c12.epub --language zh-cn --voice zho/adult/male/yunxi_24000.wav --output_dir tmp


python app.py --headless --ebook ebooks/god-c1.txt --language zho --voice voices/zho/adult/male/yunxi_24000.wav --output_dir tmp

python app.py --headless --ebook ebooks/god-1.txt --device mps --tts_engine xtts --language zho --voice voices/zho/adult/male/yunxi_24000.wav --output_dir tmp 
python app.py --headless --ebook ebooks/god-1.txt --device mps --tts_engine bark --language zho --voice voices/zho/adult/male/yunxi_24000.wav --output_dir tmp

python app.py --headless --ebook ebooks/god-1.txt --device gpu --tts_engine xtts --language zho --voice voices/zho/adult/male/yunxi_24000.wav --output_dir tmp
python app.py --headless --ebook ebooks/god-1.txt --device gpu --tts_engine bark --language zho --voice voices/zho/adult/male/yunxi_24000.wav --output_dir tmp

python app.py --headless --ebook ebooks/UnravelMe_one_sentense.txt --device gpu --tts_engine bark --output_dir tmp

uv add torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu129
uv pip install torch torchvision --index-url https://download.pytorch.org/whl/cu129


# For CUDA 12.8
uv pip install --no-cache-dir torch==2.7.0 torchvision==0.22.0 torchaudio==2.7.0 --index-url https://download.pytorch.org/whl/cu128

# For CUDA 11.8
pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# For CUDA 12.1
pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121