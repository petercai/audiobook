import os
import shutil
import subprocess
import sys
import traceback

import gradio as gr
import pymupdf4llm
import regex as re
from tqdm import tqdm

from lib import TTS_SML, default_audio_proc_format, ebook_formats
from lib.classes.tts_manager import TTSManager
from lib.ebook_audio import combine_audio_sentences

is_gui_process = False

class DependencyError(Exception):
    def __init__(self, message=None):
        super().__init__(message)
        print(message)
        # Automatically handle the exception when it's raised
        self.handle_exception()

    def handle_exception(self):
        # Print the full traceback of the exception
        traceback.print_exc()      
        # Print the exception message
        error = f'Caught DependencyError: {self}'
        print(error)    
        # Exit the script if it's not a web process
        if not is_gui_process:
            sys.exit(1)

def convert2epub(id, context):
    session = context.get_session(id)
    if session['cancellation_requested']:
        print('Cancel requested')
        return False
    try:
        title = False
        author = False
        util_app = shutil.which('ebook-convert')
        if not util_app:
            error = "The 'ebook-convert' utility is not installed or not found."
            print(error)
            return False
        file_input = session['ebook']
        if os.path.getsize(file_input) == 0:
            error = f"Input file is empty: {file_input}"
            print(error)
            return False
        file_ext = os.path.splitext(file_input)[1].lower()
        if file_ext not in ebook_formats:
            error = f'Unsupported file format: {file_ext}'
            print(error)
            return False
        if file_ext == '.pdf':
            import fitz
            msg = 'File input is a PDF. flatten it in MarkDown...'
            print(msg)
            doc = fitz.open(session['ebook'])
            pdf_metadata = doc.metadata
            filename_no_ext = os.path.splitext(os.path.basename(session['ebook']))[0]
            title = pdf_metadata.get('title') or filename_no_ext
            author = pdf_metadata.get('author') or False
            markdown_text = pymupdf4llm.to_markdown(session['ebook'])
            # Remove single asterisks for italics (but not bold **)
            markdown_text = re.sub(r'(?<!\*)\*(?!\*)(.*?)\*(?!\*)', r'\1', markdown_text)
            # Remove single underscores for italics (but not bold __)
            markdown_text = re.sub(r'(?<!_)_(?!_)(.*?)_(?!_)', r'\1', markdown_text)
            file_input = os.path.join(session['process_dir'], f'{filename_no_ext}.md')
            with open(file_input, "w", encoding="utf-8") as html_file:
                html_file.write(markdown_text)
        msg = f"Running command: {util_app} {file_input} {session['epub_path']}"
        print(msg)
        cmd = [
                util_app, file_input, session['epub_path'],
                '--input-encoding=utf-8',
                '--output-profile=generic_eink',
                '--epub-version=3',
                '--flow-size=0',
                '--chapter-mark=pagebreak',
                '--page-breaks-before', "//*[name()='h1' or name()='h2' or name()='h3' or name()='h4' or name()='h5']",
                '--disable-font-rescaling',
                '--pretty-print',
                '--smarten-punctuation',
                '--verbose'
            ]
        if title:
            cmd += ['--title', title]
        if author:
            cmd += ['--authors', author]
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
        )
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Subprocess error: {e.stderr}")
        DependencyError(e)
        return False
    except FileNotFoundError as e:
        print(f"Utility not found: {e}")
        DependencyError(e)
        return False

def convert_chapters2audio(id, context):
    session = context.get_session(id)
    try:
        if session['cancellation_requested']:
            print('Cancel requested')
            return False
        tts_manager = TTSManager(session)
        if not tts_manager:
            error = f"TTS engine {session['tts_engine']} could not be loaded!\nPossible reason can be not enough VRAM/RAM memory.\nTry to lower max_tts_in_memory in ./lib/models.py"
            print(error)
            return False
        resume_chapter = 0
        missing_chapters = []
        resume_sentence = 0
        missing_sentences = []
        existing_chapters = sorted(
            [f for f in os.listdir(session['chapters_dir']) if f.endswith(f'.{default_audio_proc_format}')],
            key=lambda x: int(re.search(r'\d+', x).group())
        )
        if existing_chapters:
            resume_chapter = max(int(re.search(r'\d+', f).group()) for f in existing_chapters) 
            msg = f'Resuming from chapter {resume_chapter}'
            print(msg)
            existing_chapter_numbers = {int(re.search(r'\d+', f).group()) for f in existing_chapters}
            missing_chapters = [
                i for i in range(1, resume_chapter) if i not in existing_chapter_numbers
            ]
            if resume_chapter not in missing_chapters:
                missing_chapters.append(resume_chapter)
        existing_sentences = sorted(
            [f for f in os.listdir(session['chapters_dir_sentences']) if f.endswith(f'.{default_audio_proc_format}')],
            key=lambda x: int(re.search(r'\d+', x).group())
        )
        if existing_sentences:
            resume_sentence = max(int(re.search(r'\d+', f).group()) for f in existing_sentences)
            msg = f"Resuming from sentence {resume_sentence}"
            print(msg)
            existing_sentence_numbers = {int(re.search(r'\d+', f).group()) for f in existing_sentences}
            missing_sentences = [
                i for i in range(1, resume_sentence) if i not in existing_sentence_numbers
            ]
            if resume_sentence not in missing_sentences:
                missing_sentences.append(resume_sentence)
        total_chapters = len(session['chapters'])
        if total_chapters == 0:
            error = 'No chapterrs found!'
            print(error)
            return False
        total_iterations = sum(len(session['chapters'][x]) for x in range(total_chapters))
        total_sentences = sum(sum(1 for row in chapter if row.strip() not in TTS_SML.values()) for chapter in session['chapters'])
        if total_sentences == 0:
            error = 'No sentences found!'
            print(error)
            return False           
        sentence_number = 0
        msg = f"--------------------------------------------------\nA total of {total_chapters} {'chapter' if total_chapters <= 1 else 'blocks'} and {total_sentences} {'sentence' if total_sentences <= 1 else 'sentences'}.\n--------------------------------------------------"
        print(msg)
        progress_bar = gr.Progress(track_tqdm=False)
        with tqdm(total=total_iterations, desc='0.00%', bar_format='{desc}: {n_fmt}/{total_fmt} ', unit='step', initial=0) as t:
            for x in range(0, total_chapters):
                chapter_num = x + 1
                chapter_audio_file = f'chapter_{chapter_num}.{default_audio_proc_format}'
                sentences = session['chapters'][x]
                sentences_count = sum(1 for row in sentences if row.strip() not in TTS_SML.values())
                start = sentence_number
                msg = f'Chapter {chapter_num} containing {sentences_count} sentences...'
                print(msg)
                for i, sentence in enumerate(sentences):
                    if session['cancellation_requested']:
                        msg = 'Cancel requested'
                        print(msg)
                        return False
                    if sentence_number in missing_sentences or sentence_number > resume_sentence or (sentence_number == 0 and resume_sentence == 0):
                        if sentence_number <= resume_sentence and sentence_number > 0:
                            msg = f'**Recovering missing file sentence {sentence_number}'
                            print(msg)
                        sentence = sentence.strip()
                        success = tts_manager.convert_sentence2audio(sentence_number, sentence) if sentence else True
                        if success:
                            total_progress = (t.n + 1) / total_iterations
                            progress_bar(total_progress)
                            is_sentence = sentence.strip() not in TTS_SML.values()
                            percentage = total_progress * 100
                            t.set_description(f'{percentage:.2f}%')
                            msg = f" | {sentence}" if is_sentence else f" | {sentence}"
                            print(msg)
                        else:
                            return False
                    if sentence.strip() not in TTS_SML.values():
                        sentence_number += 1
                    t.update(1)  # advance for every iteration, including SML
                end = sentence_number - 1 if sentence_number > 1 else sentence_number
                msg = f"End of chapter {chapter_num}"
                print(msg)
                if chapter_num in missing_chapters or sentence_number > resume_sentence:
                    if chapter_num <= resume_chapter:
                        msg = f'**Recovering missing file chapter {chapter_num}'
                        print(msg)
                    if combine_audio_sentences(chapter_audio_file, start, end, session):
                        msg = f'Combining chapter {chapter_num} to audio, sentence {start} to {end}'
                        print(msg)
                    else:
                        msg = 'combine_audio_sentences() failed!'
                        print(msg)
                        return False
        return True
    except Exception as e:
        DependencyError(e)
        return False
