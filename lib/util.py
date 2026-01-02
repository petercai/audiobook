import inspect
import os
import re
import sys


class util:
    @staticmethod
    def sanitize_filename(str, replacement="_"):
        str = str.replace('&', 'And')
        forbidden_chars = r'[<>:"/\\|?*\x00-\x1F ()]'
        sanitized = re.sub(r'\s+', replacement, str)
        sanitized = re.sub(forbidden_chars, replacement, sanitized)
        sanitized = sanitized.strip("_")
        return sanitized

    @staticmethod
    def save_transcript_by_chapter(chapters_in_book, chapter_dir):
        chapter_count = len(chapters_in_book)
        number_width = max(1, len(str(chapter_count)))
        for chapter_index, chapter_sentences in enumerate(chapters_in_book, 1):
            chapter_filename = f"chapter_{chapter_index:0{number_width}d}.txt"
            chapter_path = os.path.join(chapter_dir, chapter_filename)
            with open(chapter_path, "w", encoding="utf-8") as chapter_file:
                chapter_file.write("\n".join(chapter_sentences))
        return chapter_count
    
    @staticmethod
    def print_error(e: Exception):
        if isinstance(e, Exception):
            # Get where exception was raised
            exc_type, exc_obj, exc_tb = sys.exc_info()
            raised_fname = exc_tb.tb_frame.f_code.co_filename
            raised_lineno = exc_tb.tb_lineno
            print(f"Error raised in {raised_fname}:{raised_lineno} - {e}")
            
            frame = inspect.currentframe()
            caller_frame = frame.f_back
            catch_fname = os.path.basename(caller_frame.f_code.co_filename)
            catch_lineno = caller_frame.f_lineno
            print(f"Error caught in {catch_fname}:{catch_lineno} - {e}")
