python app.py

pip install -r requirements.txt --proxy http://webproxy.bns:8080 --trusted-host pypi.org --trusted-host files.pythonhosted.org
pip install -r requirements.txt --proxy http://localhost:9000 --trusted-host pypi.org --trusted-host files.pythonhosted.org

python app.py --headless --ebook ebooks/god-c1.txt --language zh-cn --voice zho/adult/male/yunyang_24000.wav --output_dir audiobook_output