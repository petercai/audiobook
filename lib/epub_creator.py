import os
import shutil
import subprocess

import pymupdf4llm
import regex as re

from lib.conf import ebook_formats
from lib.util import util


class EPubCreator:
    def convert2epub(self, session):
        """
        Converts a given ebook file to EPUB format using Calibre's ebook-convert tool.
        
        If the input file is already in EPUB format, it will be directly used without conversion.
        This method handles various input formats and prepares them for conversion.
        If the input is a PDF, it first converts it to Markdown to improve text extraction,
        then proceeds with the EPUB conversion. It relies on the external `ebook-convert`
        command-line utility.

        Args:
            id (str): The session ID for the current conversion process.
            context (SessionContext): The context object containing session data.

        Returns:
            bool: True if the conversion to EPUB was successful, False otherwise.

        Session Fields:
            - cancellation_requested (bool): Flag to check if the conversion process should be cancelled.
            - ebook (str): The absolute path to the source ebook file.
            - process_dir (str): The directory path for storing intermediate files during conversion.
            - epub_path (str): The target absolute path for the converted EPUB file.
        """
        if session['cancellation_requested']:
            print('Cancel requested')
            return False

        file_input = session['ebook']
        process_dir = session['process_dir']
        epub_output_file = session['epub_path']
        file_ext = os.path.splitext(file_input)[1].lower()
        if file_ext == '.epub':
            print("Input file is already in EPUB format. Skipping conversion.")
            if not os.path.exists(epub_output_file) or not os.path.samefile(file_input, epub_output_file):
                shutil.copy(file_input, epub_output_file)
            return True

        try:
            title = False
            author = False
            util_app = shutil.which('ebook-convert')
            if not util_app:
                error = "The 'ebook-convert' utility is not installed or not found."
                print(error)
                return False
            if os.path.getsize(file_input) == 0:
                error = f"Input file is empty: {file_input}"
                print(error)
                return False
            if file_ext not in ebook_formats:
                error = f'Unsupported file format: {file_ext}'
                print(error)
                return False
            if file_ext == '.pdf':
                import fitz
                msg = 'File input is a PDF. flatten it in MarkDown...'
                print(msg)
                doc = fitz.open(file_input)
                pdf_metadata = doc.metadata
                filename_no_ext = os.path.splitext(os.path.basename(file_input))[0]
                title = pdf_metadata.get('title') or filename_no_ext
                author = pdf_metadata.get('author') or False
                markdown_text = pymupdf4llm.to_markdown(file_input)
                markdown_text = re.sub(r'(?<!\*)\*(?!\*)(.*?)\*(?!\*)', r'\1', markdown_text)
                markdown_text = re.sub(r'(?<!_)_(?!_)(.*?)_(?!_)', r'\1', markdown_text)
                file_input = os.path.join(process_dir, f'{filename_no_ext}.md')
                with open(file_input, "w", encoding="utf-8") as html_file:
                    html_file.write(markdown_text)
            msg = f"Running command: {util_app} {file_input} {epub_output_file}"
            print(msg)
            cmd = [
                util_app, file_input, epub_output_file,
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
            error = f"Subprocess error: {e.stderr}"
            util.print_error(e, error)
            return False
        except FileNotFoundError as e:
            error = f"Utility not found: {e}"
            util.print_error(e, error)
            return False
