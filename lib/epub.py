import os
import shutil
import subprocess
import sys
import traceback
import pymupdf4llm
import regex as re

from lib import ebook_formats

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
