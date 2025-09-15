python app.py

pip install -r requirements.txt --proxy http://webproxy.bns:8080 --trusted-host pypi.org --trusted-host files.pythonhosted.org
pip install -r requirements.txt --proxy http://localhost:9000 --trusted-host pypi.org --trusted-host files.pythonhosted.org

python app.py --headless --ebook ebooks/god-c1.txt --language zh-cn --voice zho/adult/male/yunxi_24000.wav --output_dir tmp
python app.py --headless --ebook ebooks/god-c12.epub --language zh-cn --voice zho/adult/male/yunxi_24000.wav --output_dir tmp


python app.py --headless --ebook ebooks/god-c1.txt --language zho --voice voices/zho/adult/male/yunxi_24000.wav --output_dir tmp

python app.py --headless --ebook ebooks/god-1.txt --device mps --tts_engine xtts --language zho --voice voices/zho/adult/male/yunxi_24000.wav --output_dir tmp 
python app.py --headless --ebook ebooks/god-1.txt --device mps --tts_engine bark --language zho --voice voices/zho/adult/male/yunxi_24000.wav --output_dir tmp
