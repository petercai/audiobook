#!/bin/sh
python app.py
ebook_path="$1"
book_name="${ebook_path##*/}"
book_name="${book_name%.*}"

python app.py --headless \
  --script_mode \
  --session "$book_name" \
  --ebook "$ebook_path" \
  --device cpu \
  --add_toc_title \
  --language en \
  --tts_engine xtts \
  --fine_tuned DermotCrowley \
  --output_format mp4
