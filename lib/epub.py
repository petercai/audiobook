import io
import math
import os
import shutil
import subprocess

import ebooklib
import gradio as gr
import pymupdf4llm
import regex as re
import stanza
import unicodedata
from PIL import Image
from bs4 import BeautifulSoup, NavigableString, Tag
from num2words import num2words
from tqdm import tqdm

from lib.classes.tts_manager import TTSManager
from lib.conf import default_audio_proc_format, ebook_formats, models_dir
from lib.ebook_audio import EbookAudio
from lib.functions import DependencyError
from lib.lang import abbreviations_mapping, year_to_decades_languages, language_mapping, specialchars_remove, \
    language_clock, language_math_phonemes, default_language_code, roman_numbers_tuples, emojis_list, \
    punctuation_switch, punctuation_split_hard_set, punctuation_list_set, punctuation_split_soft_set, \
    specialchars_mapping
from lib.models import TTS_SML

is_gui_process = False

class EPubProcessor:

    def __init__(self):
        self.ebook_audio = EbookAudio()
        self.heading_tags = {"h1", "h2", "h3", "h4", "h5", "h6"}
        self.break_tags = {"p", "div", "li", "br", "hr"}
        self.pause_tags = {"ol", "ul"}
        self.proc_tags = {
            "p", "div", "span", "a", "li", "ol", "ul", "i", "b", "em",
            "strong", "blockquote", "q", "cite", "code", "pre", "br", "hr"
        } | self.heading_tags | self.break_tags | self.pause_tags
        self.sml_tokens = set(TTS_SML.values())

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
        # Retrieve the session data using the provided ID.
        # session = context.get_session(id)
        # Check for a cancellation request before starting the process.
        if session['cancellation_requested']:
            print('Cancel requested')
            return False
        # Get the input file path, process directory, and target EPUB path from the session.
        file_input = session['ebook']
        process_dir = session['process_dir']
        epub_output_file = session['epub_path']
        # Get the file extension to determine the input format.
        file_ext = os.path.splitext(file_input)[1].lower()
        # If the input file is already an EPUB, just copy it and return.
        if file_ext == '.epub':
            print("Input file is already in EPUB format. Skipping conversion.")
            if not os.path.exists(epub_output_file) or not os.path.samefile(file_input, epub_output_file):
                shutil.copy(file_input, epub_output_file)
            return True
        try:
            # Initialize title and author as False. They will be set if the input is a PDF.
            title = False
            author = False
            # Locate the 'ebook-convert' utility from Calibre in the system's PATH.
            util_app = shutil.which('ebook-convert')
            # If the utility is not found, the conversion cannot proceed.
            if not util_app:
                error = "The 'ebook-convert' utility is not installed or not found."
                print(error)
                return False
            # Check if the input file is empty.
            if os.path.getsize(file_input) == 0:
                error = f"Input file is empty: {file_input}"
                print(error)
                return False
            # Validate if the file format is supported.
            if file_ext not in ebook_formats:
                error = f'Unsupported file format: {file_ext}'
                print(error)
                return False
            # Special handling for PDF files to improve text extraction.
            if file_ext == '.pdf':
                import fitz
                msg = 'File input is a PDF. flatten it in MarkDown...'
                print(msg)
                # Open the PDF and extract metadata.
                doc = fitz.open(file_input)
                pdf_metadata = doc.metadata
                filename_no_ext = os.path.splitext(os.path.basename(file_input))[0]
                # Use PDF metadata for title and author, with fallbacks.
                title = pdf_metadata.get('title') or filename_no_ext
                author = pdf_metadata.get('author') or False
                # Convert the PDF content to Markdown format.
                markdown_text = pymupdf4llm.to_markdown(file_input)
                # Clean up the Markdown: remove single asterisks and underscores used for italics.
                markdown_text = re.sub(r'(?<!\*)\*(?!\*)(.*?)\*(?!\*)', r'\1', markdown_text)
                markdown_text = re.sub(r'(?<!_)_(?!_)(.*?)_(?!_)', r'\1', markdown_text)
                # Save the Markdown content to a new file, which will be used as input for conversion.
                file_input = os.path.join(process_dir, f'{filename_no_ext}.md')
                with open(file_input, "w", encoding="utf-8") as html_file:
                    html_file.write(markdown_text)
            # Log the command that will be executed.
            msg = f"Running command: {util_app} {file_input} {epub_output_file}"
            print(msg)
            # Construct the command for the ebook-convert utility with various options for a clean EPUB3.
            cmd = [
                    util_app, file_input, epub_output_file,
                    '--input-encoding=utf-8',  # Specify input encoding.
                    '--output-profile=generic_eink',  # Profile for e-ink devices.
                    '--epub-version=3',  # Ensure EPUB3 output.
                    '--flow-size=0',  # Disable splitting of files by size.
                    '--chapter-mark=pagebreak',  # Use page breaks to mark chapters.
                    '--page-breaks-before', "//*[name()='h1' or name()='h2' or name()='h3' or name()='h4' or name()='h5']",  # Insert page breaks before headings.
                    '--disable-font-rescaling',  # Prevent font size changes.
                    '--pretty-print',  # Format the output HTML/XML nicely.
                    '--smarten-punctuation',  # Convert plain quotes, dashes, etc., to typographic equivalents.
                    '--verbose'  # Get detailed output from the tool.
                ]
            # If a title was extracted from PDF metadata, add it to the command.
            if title:
                cmd += ['--title', title]
            # If an author was extracted, add it to the command.
            if author:
                cmd += ['--authors', author]
            # Execute the conversion command.
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8'
            )
            # Print the output from the conversion process.
            print(result.stdout)
            # Return True on successful conversion.
            return True
        except subprocess.CalledProcessError as e:
            # Handle errors from the subprocess.
            print(f"Subprocess error: {e.stderr}")
            DependencyError(e)
            return False
        except FileNotFoundError as e:
            # Handle the case where the ebook-convert utility is not found.
            print(f"Utility not found: {e}")
            DependencyError(e)
            return False

    def get_ebook_title(self, epubBook, all_docs):
        # 1. Try metadata (official EPUB title)
        meta_title = epubBook.get_metadata("DC", "title")
        if meta_title and meta_title[0][0].strip():
            return meta_title[0][0].strip()
        # 2. Try <title> in the head of the first XHTML document
        if all_docs:
            html = all_docs[0].get_content().decode("utf-8")
            soup = BeautifulSoup(html, "html.parser")
            title_tag = soup.select_one("head > title")
            if title_tag and title_tag.text.strip():
                return title_tag.text.strip()
            # 3. Try <img alt="..."> if no visible <title>
            img = soup.find("img", alt=True)
            if img:
                alt = img['alt'].strip()
                if alt and "cover" not in alt.lower():
                    return alt
        return None

    def get_cover(self, epubBook, session):
        try:
            if session['cancellation_requested']:
                msg = 'Cancel requested'
                print(msg)
                return False
            cover_image = None
            cover_path = os.path.join(session['process_dir'], session['filename_noext'] + '.jpg')
            for item in epubBook.get_items_of_type(ebooklib.ITEM_COVER):
                cover_image = item.get_content()
                break
            if not cover_image:
                for item in epubBook.get_items_of_type(ebooklib.ITEM_IMAGE):
                    if 'cover' in item.file_name.lower() or 'cover' in item.get_id().lower():
                        cover_image = item.get_content()
                        break
            if cover_image:
                # Open the image from bytes
                image = Image.open(io.BytesIO(cover_image))
                # Convert to RGB if needed (JPEG doesn't support alpha)
                if image.mode in ('RGBA', 'P'):
                    image = image.convert('RGB')
                image.save(cover_path, format='JPEG')
                return cover_path
            return True
        except Exception as e:
            DependencyError(e)
            return False

    def get_chapters_in_sentenses(self, epubBook, session):
        """
        Extract and process chapters from an EPUB book for text-to-speech conversion.
        
        This method orchestrates the extraction and processing of chapters from an EPUB file.
        It handles language-specific processing, downloads required NLP models, converts
        numerical content to words, and prepares text for TTS generation.
        
        Args:
            epubBook: An ebooklib.epub.EpubBook object representing the EPUB file
            session (dict): A dictionary containing session information including:
                - 'cancellation_requested' (bool): Whether cancellation was requested
                - 'language_iso1' (str): ISO 639-1 language code (e.g., 'en', 'fr')
                - 'language' (str): Full language code (e.g., 'eng', 'fra')
                - 'tts_engine' (str): Text-to-speech engine identifier
                - Other session-specific data
                
        Returns:
            tuple: A tuple containing:
                - toc (list): Table of contents entries as strings
                - chapters (list): List of processed chapters, where each chapter is a list of sentences
                
        Returns (None, None) if an error occurs or no chapters are found.
        """
        try:
            # Check if the operation has been cancelled before starting
            if session['cancellation_requested']:
                print('Cancel requested')
                return False
                
            # Extract language information from session for processing
            language_iso_ = session['language_iso1']  # e.g., 'en'
            language_ = session['language']            # e.g., 'eng'
            tts_engine_ = session['tts_engine']
            
            # Step 1: Extract TOC (Table of Contents) and document list
            # Get all documents in reading order and the table of contents
            all_docs, toc = self.get_epub_chapters(epubBook, language_)
            if not all_docs:
                return [], []
                
            # Attempt to extract the book title for metadata
            title = self.get_ebook_title(epubBook, all_docs)
            
            # Initialize the chapters list to store processed content
            # todo: toc and chapter should be a list of dicts
            chapters = []
            
            # Initialize Stanza NLP pipeline for languages that require advanced processing
            # This is used for date recognition and other NLP tasks
            stanza_nlp = False
            if language_ in year_to_decades_languages:
                try:
                    # Download the required language model if not already present
                    stanza.download(language_iso_, dir=os.path.join(models_dir, 'stanza'), logging_level='WARN', verbose=False if session['offline_mode'] else None)
                except Exception as e:
                    if session['offline_mode']:
                        print(f"Offline mode: Failed to find stanza model for '{language_iso_}'. Expected in '{os.path.join(models_dir, 'stanza')}'")
                    raise e
                # Create a processing pipeline for tokenization and named entity recognition
                stanza_nlp = stanza.Pipeline(language_iso_, processors='tokenize,ner')
                
            # Check if the num2words library supports the current language
            # This determines how numbers will be converted to words
            is_num2words_compat = self._get_num2words_compat(language_iso_)
            
            # Inform user that numerical and mathematical content analysis is beginning
            msg = 'Analyzing numbers, maths signs, dates and time to convert in words...'
            print(msg)
            
            # Process each document (chapter) in the EPUB
            for doc in all_docs:
                # Process the chapter content with various text transformations
                # This includes number conversion, punctuation handling, and sentence segmentation
                sentences_list = self.filter_chapter(
                    doc, 
                    language_, 
                    language_iso_, 
                    tts_engine_, 
                    stanza_nlp, 
                    is_num2words_compat
                )
                
                # Handle the result of chapter processing
                if sentences_list is None:
                    # If processing failed, stop further processing
                    break
                elif len(sentences_list) > 0:
                    # If successfully processed and contains content, add to chapters
                    chapters.append(sentences_list)
                    
            # Verify that at least one chapter was successfully processed
            if len(chapters) == 0:
                error = 'No chapters found!'
                return None, None
                
            # Return the table of contents and processed chapters
            return toc, chapters
            
        except Exception as e:
            # Handle any unexpected errors during processing
            error = f'Error extracting main content pages: {e}'
            DependencyError(error)
            return None, None

    def get_epub_chapters(self, epubBook, language_):
        try:
            toc = epubBook.toc  # Extract TOC
            toc_list = []
            for item in toc:
                if hasattr(item, 'title'):
                    normalized_title = self.normalize_text(
                        str(item.title),
                        language_,
                    )
                    if normalized_title is not None:
                        toc_list.append(normalized_title)
        except Exception as toc_error:
            error = f"Error extracting TOC: {toc_error}"
            print(error)
        # Get spine item IDs
        spine_ids = [item[0] for item in epubBook.spine]
        # Filter only spine documents (i.e., reading order)
        all_docs = [
            item for item in epubBook.get_items_of_type(ebooklib.ITEM_DOCUMENT)
            if item.id in spine_ids
        ]
        return all_docs, toc

    def _num_repl(self, m, lang, lang_iso1, is_num2words_compat):
        s = m.group(0)
        # leave years alone (already handled above)
        if re.fullmatch(r"\d{4}", s):
            return s
        n = float(s) if "." in s else int(s)
        if is_num2words_compat:
            return num2words(n, lang=(lang_iso1 or "en"))
        else:
            return self._math2words(m, lang, lang_iso1, None, is_num2words_compat)

    def _tuple_row(self, node, last_text_char=None):
        try:
            for child in node.children:
                if isinstance(child, NavigableString):
                    text = child.strip()
                    if text:
                        yield ("text", text)
                        last_text_char = text[-1] if text else last_text_char

                elif isinstance(child, Tag):
                    name = child.name.lower()
                    if name in self.heading_tags:
                        title = child.get_text(strip=True)
                        if title:
                            yield ("heading", title)
                            last_text_char = title[-1] if title else last_text_char

                    elif name == "table":
                        yield ("table", child)

                    else:
                        return_data = False
                        if name in self.proc_tags:
                            for inner in self._tuple_row(child, last_text_char):
                                return_data = True
                                yield inner
                                # Track last char if this is text or heading
                                if inner[0] in ("text", "heading") and inner[1]:
                                    last_text_char = inner[1][-1]

                            if return_data:
                                if name in self.break_tags:
                                    # Only yield break if last char is NOT alnum or space
                                    if not (last_text_char and (last_text_char.isalnum() or last_text_char.isspace())):
                                        yield ("break", TTS_SML['break'])
                                elif name in self.heading_tags or name in self.pause_tags:
                                    yield ("pause", TTS_SML['pause'])

                        else:
                            yield from self._tuple_row(child, last_text_char)

        except Exception as e:
            error = f'filter_chapter() tuple_row() error: {e}'
            DependencyError(error)
            return None

    def filter_chapter(self, doc, lang, lang_iso1, tts_engine, stanza_nlp, is_num2words_compat):
        """
        Process an EPUB chapter document and convert it into a list of properly formatted sentences
        ready for text-to-speech conversion.
        
        This method performs several key operations:
        1. Parses the HTML content of the chapter
        2. Filters out non-content sections (TOC, front matter, etc.)
        3. Extracts structured content (headings, text, tables)
        4. Processes and normalizes text (numbers, dates, Roman numerals, etc.)
        5. Segments text into appropriately sized sentences for TTS
        
        Args:
            doc: ebooklib document object representing a chapter
            lang: Language code (e.g., 'eng', 'fra')
            lang_iso1: ISO 639-1 language code (e.g., 'en', 'fr')
            tts_engine: Text-to-speech engine identifier
            stanza_nlp: Stanza NLP pipeline for advanced text processing
            is_num2words_compat: Boolean indicating if num2words library supports the language
            
        Returns:
            list: List of processed sentences ready for TTS conversion, or None if errors occur
        """
        try:
            # Decode the HTML content of the chapter from the ebook document.
            raw_html = doc.get_content().decode("utf-8")
            # Parse the HTML using BeautifulSoup to create a navigable structure.
            soup = BeautifulSoup(raw_html, 'html.parser')
            # Determine the root element for content extraction.
            # If a `body` tag exists, use it. Otherwise, use the whole document (`soup`).
            # This handles cases where the EPUB page is a fragment without a `body` tag.
            content_root = soup.body if soup.body else soup
            # If the chapter body is empty or contains no text, skip it by returning an empty list.
            if not content_root or not content_root.get_text(strip=True):
                return []
            # Check the EPUB type to exclude non-content sections like TOC, frontmatter, etc.
            # This helps filter out pages that shouldn't be read aloud (like table of contents).
            epub_type = ""
            if soup.body:
                epub_type = soup.body.get("epub:type", "").lower()
            # If epub:type is not specified on body, check for section tag with epub:type
            if not epub_type:
                section_tag = content_root.find("section")
                if section_tag:
                    epub_type = section_tag.get("epub:type", "").lower()
            # Define a set of excluded content types that shouldn't be processed
            excluded = {
                "frontmatter", "backmatter", "toc", "titlepage", "colophon",
                "acknowledgments", "dedication", "glossary", "index",
                "appendix", "bibliography", "copyright-page", "landmark"
            }
            # If the epub_type contains any excluded terms, skip this chapter
            if any(part in epub_type for part in excluded):
                return []
            # Remove script and style tags as they don't contain readable content for TTS.
            for tag in content_root.find_all(["script", "style"]):
                tag.decompose()
            # Recursively traverse the HTML body to extract content into a structured list of tuples.
            # Each tuple contains a type identifier and the corresponding content.
            tuples_list = list(self._tuple_row(content_root))
            if not tuples_list:
                error = 'No tuples_list from content_root created!'
                print(error)
                return None
            # Process the structured list to build a flat list of text elements.
            text_list = []
            handled_tables = set()  # Keep track of tables we've already processed
            prev_typ = None  # Track the previous element type to avoid duplicate breaks/pauses
            for typ, payload in tuples_list:
                if typ == "heading":
                    # Add heading text to the list after stripping whitespace
                    text_list.append(payload.strip())
                elif typ == "break":
                    # Avoid adding multiple consecutive break tokens which could cause unwanted pauses
                    if prev_typ != 'break':
                        text_list.append(TTS_SML['break'])
                elif typ == 'pause':
                    # Avoid adding multiple consecutive pause tokens which could cause unwanted pauses
                    if prev_typ != 'pause':
                        text_list.append(TTS_SML['pause'])
                elif typ == "table":
                    # Convert HTML tables into a readable string format for TTS
                    table = payload
                    # Skip if we've already processed this table (to avoid duplicates)
                    if table in handled_tables:
                        prev_typ = typ
                        continue
                    handled_tables.add(table)
                    # Find all table rows
                    rows = table.find_all("tr")
                    if not rows:
                        prev_typ = typ
                        continue
                    # Extract header cells text (both th and td in first row)
                    headers = [c.get_text(strip=True) for c in rows[0].find_all(["td", "th"])]
                    # Process each data row after the header
                    for row in rows[1:]:
                        # Extract cell texts, replacing non-breaking spaces with regular spaces
                        cells = [c.get_text(strip=True).replace('\xa0', ' ') for c in row.find_all("td")]
                        if not cells:
                            continue
                        # Format the row data - if headers exist and match cell count, use labeled format
                        if len(cells) == len(headers) and headers:
                            line = " — ".join(f"{h}: {c}" for h, c in zip(headers, cells))
                        else:
                            # Otherwise, just join the cells with separators
                            line = " — ".join(cells)
                        if line:
                            text_list.append(line.strip())
                else:
                    # Handle regular text content
                    text = payload.strip()
                    if text:
                        text_list.append(text)
                prev_typ = typ
            # Get the maximum character limit for the current language to ensure proper sentence segmentation
            max_chars = language_mapping[lang]['max_chars'] - 4
            # Clean the list by merging short sentences that were separated by a break.
            # This helps create more natural speech flow by avoiding too many short utterances.
            clean_list = []
            i = 0
            while i < len(text_list):
                current = text_list[i]
                # Check if the current item is a break token
                if current == "‡break‡":
                    if clean_list:
                        prev = clean_list[-1]
                        # Skip consecutive break or pause tokens
                        if prev in ("‡break‡", "‡pause‡"):
                            i += 1
                            continue
                        # If the previous text ends with alphanumeric or space, try to merge with next sentence
                        if prev and (prev[-1].isalnum() or prev[-1] == ' '):
                            if i + 1 < len(text_list):
                                next_sentence = text_list[i + 1]
                                # Calculate the length if we merge the previous text with the next sentence
                                merged_length = len(prev.rstrip()) + 1 + len(next_sentence.lstrip())
                                # Merge if the combined length is within the character limit.
                                if merged_length <= max_chars:
                                    # Handle spacing between merged parts to ensure proper spacing
                                    if not prev.endswith(" ") and not next_sentence.startswith(" "):
                                        clean_list[-1] = prev + " " + next_sentence
                                    else:
                                        clean_list[-1] = prev + next_sentence
                                    i += 2
                                    continue
                                else:
                                    # If merging would exceed limit, just add the break token
                                    clean_list.append(current)
                                    i += 1
                                    continue
                clean_list.append(current)
                i += 1
            # Join the cleaned list into a single text string for further processing
            text = ' '.join(clean_list)
            # If the text is empty or contains no valid characters, return None to indicate no content
            if not re.search(r"[^\W_]", text):
                error = 'No valid text found!'
                print(error)
                return None
            # If a Stanza NLP pipeline is available, use it for advanced text processing like date recognition
            if stanza_nlp:
                # Regex for ordinal numbers (e.g., 1st, 2nd) to convert them to words
                re_ordinal = re.compile(
                    r'(?<!\w)(0?[1-9]|[12][0-9]|3[01])(?:\s|\u00A0)*(?:st|nd|rd|th)(?!\w)',
                    re.IGNORECASE
                )
                # Regex for general numbers to convert them to words
                re_num = re.compile(r'(?<!\w)[-+]?\d+(?:\.\d+)?(?!\w)')
                # Normalize Unicode characters and replace non-breaking spaces with regular spaces
                text = unicodedata.normalize('NFKC', text).replace('\u00A0', ' ')
                # Process dates if both numbers and ordinals are present in the text
                if re_num.search(text) and re_ordinal.search(text):
                    # Use Stanza NLP to identify date entities in the text
                    date_spans = self._get_date_entities(text, stanza_nlp)
                    if date_spans:
                        result = []
                        last_pos = 0
                        # Process each identified date span
                        for start, end, date_text in date_spans:
                            # Add text before the date span to the result
                            result.append(text[last_pos:start])
                            # 1) Convert 4-digit years to words using the _year2words method
                            processed = re.sub(
                                r"\b\d{4}\b",
                                lambda m: self._year2words(m.group(), lang, lang_iso1, is_num2words_compat),
                                date_text
                            )
                            # 2) Convert ordinal days to words based on num2words compatibility
                            if is_num2words_compat:
                                processed = re_ordinal.sub(
                                    lambda m: num2words(int(m.group(1)), to="ordinal", lang=(lang_iso1 or "en")),
                                    processed
                                )
                            else:
                                processed = re_ordinal.sub(
                                    lambda m: self._math2words(m.group(), lang, lang_iso1, tts_engine, is_num2words_compat),
                                    processed
                                )
                            # 3) Convert other numbers to words, skipping years which were already processed
                            processed = re_num.sub(lambda m: self._num_repl(m, lang, lang_iso1, is_num2words_compat), processed)
                            result.append(processed)
                            last_pos = end
                        # Add any remaining text after the last date span
                        result.append(text[last_pos:])
                        text = ''.join(result)
                    else:
                        # If no date entities are found, process ordinals and years separately
                        if is_num2words_compat:
                            text = re_ordinal.sub(
                                lambda m: num2words(int(m.group(1)), to="ordinal", lang=(lang_iso1 or "en")),
                                text
                            )
                        else:
                            text = re_ordinal.sub(
                                lambda m: self._math2words(int(m.group(1)), lang, lang_iso1, tts_engine, is_num2words_compat),
                                text
                            )
                        # Convert 4-digit years to words
                        text = re.sub(
                            r"\b\d{4}\b",
                            lambda m: self._year2words(m.group(), lang, lang_iso1, is_num2words_compat),
                            text
                        )
            # Convert Roman numerals, clock times, and mathematical expressions to words for better TTS
            text = self._roman2number(text)  # Convert Roman numerals to Arabic numbers
            text = self._clock2words(text, lang, lang_iso1, tts_engine, is_num2words_compat)  # Convert clock times to words
            text = self._math2words(text, lang, lang_iso1, tts_engine, is_num2words_compat)  # Convert math expressions to words
            # Remove special characters that are not needed for TTS by replacing them with spaces
            specialchars_remove_table = str.maketrans({ch: ' ' for ch in specialchars_remove})
            text = text.translate(specialchars_remove_table)
            # Perform final text normalization (e.g., handling abbreviations, punctuation) for better TTS quality
            text = self.normalize_text(text, lang)
            # Split the fully processed text into sentences for TTS based on language-specific rules
            sentences = self.get_sentences(text, lang, tts_engine)
            if len(sentences) == 0:
                error = 'No sentences found!'
                print(error)
                return None
            # Return the processed sentences for TTS conversion
            return self.get_sentences(text, lang, tts_engine)
        except Exception as e:
            error = f'filter_chapter() error: {e}'
            DependencyError(error)
            return None

    def _split_inclusive(self, text, pattern):
        result = []
        last_end = 0
        for match in pattern.finditer(text):
            result.append(text[last_end:match.end()].strip())
            last_end = match.end()
        if last_end < len(text):
            tail = text[last_end:].strip()
            if tail:
                result.append(tail)
        return result

    def _segment_ideogramms(self, text, lang):
        """
        Tokenizes text for ideogram-based languages, preserving SML tokens.

        This method splits the input text into a list of words or tokens, which is
        a necessary preprocessing step for languages that do not use spaces to
        delimit words (e.g., Chinese, Japanese, Thai). It uses different libraries
        for tokenization based on the specified language.

        Args:
            text (str): The text to be tokenized.
            lang (str): The language code, which determines the tokenization library to use.
                        Supported codes include 'zho' (Chinese), 'jpn' (Japanese),
                        'kor' (Korean), 'tha' (Thai), etc.

        Returns:
            list: A list of string tokens. If an error occurs during tokenization,
                  it returns a list containing the original text.
        """
        # Create a regex pattern to split the text by SML tokens, while keeping them.
        sml_pattern = "|".join(re.escape(token) for token in self.sml_tokens)
        segments = re.split(f"({sml_pattern})", text)
        result = []
        try:
            for segment in segments:
                if not segment:
                    continue
                # If the segment is an SML token, add it directly to the results.
                if re.fullmatch(sml_pattern, segment):
                    result.append(segment)
                else:
                    # Otherwise, apply the appropriate tokenizer based on the language.
                    if lang == 'zho':
                        import jieba
                        result.extend([t for t in jieba.cut(segment) if t.strip()])
                    elif lang == 'jpn':
                        from sudachipy import dictionary, tokenizer
                        sudachi = dictionary.Dictionary().create()
                        mode = tokenizer.Tokenizer.SplitMode.C
                        result.extend([m.surface() for m in sudachi.tokenize(segment, mode) if m.surface().strip()])
                    elif lang == 'kor':
                        from korean_tokenizer import LTokenizer
                        ltokenizer = LTokenizer()
                        result.extend([t for t in ltokenizer.tokenize(segment) if t.strip()])
                    elif lang in ['tha', 'lao', 'mya', 'khm']:
                        from pythainlp import word_tokenize
                        result.extend([t for t in word_tokenize(segment, engine='newmm') if t.strip()])
                    else:
                        # If the language is not one of the specified ideogrammatic languages,
                        # treat the segment as a single token.
                        result.append(segment.strip())
            return result
        except Exception as e:
            # If any error occurs (e.g., a tokenizer library is not installed),
            # fall back to returning the original text as a single-item list.
            DependencyError(e)
            return [text]

    def _join_ideogramms(self, idg_list, max_chars):
        """
        Joins a list of ideogrammatic tokens into sentences that respect a maximum
        character length.

        This generator function is designed for languages like Chinese, Japanese, and
        Korean, where text is first tokenized into words. It reconstructs sentences
        from these tokens, ensuring that no single yielded sentence exceeds the
        `max_chars` limit. It also preserves SML tokens as separate items.

        Args:
            idg_list (list): A list of string tokens (words, punctuation, SML tokens).
            max_chars (int): The maximum number of characters allowed per sentence.

        Yields:
            str: A sentence or SML token, formatted and constrained by length.
        """
        try:
            buffer = ''
            for token in idg_list:
                # 1) On SML token: flush the current buffer, then yield the token separately.
                if token.strip() in self.sml_tokens:
                    if buffer:
                        yield buffer
                        buffer = ''
                    yield token
                    continue
                # 2) If adding the next token would overflow the max character limit, flush the current buffer.
                if buffer and len(buffer) + len(token) > max_chars:
                    yield buffer
                    buffer = ''
                # 3) Append the token to the buffer.
                buffer += token
            # 4) After the loop, flush any remaining text in the buffer.
            if buffer:
                yield buffer
        except Exception as e:
            DependencyError(e)
            if buffer:
                yield buffer

    def _repl_abbreviations(self, match: re.Match, mapping) -> str:
        token = match.group(1)
        for k, expansion in mapping.items():
            if token.lower() == k.lower():
                return expansion
        return token  # fallback

    def _n2w(self, n: int, lang_lc, is_num2words_compat, tts_engine, lang, lang_iso1) -> str:
        _n2w_cache = {}
        key = (n, lang_lc, is_num2words_compat)
        if key in _n2w_cache:
            return _n2w_cache[key]
        if is_num2words_compat:
            word = num2words(n, lang=lang_lc)
        else:
            word = self._math2words(n, lang, lang_iso1, tts_engine, is_num2words_compat)
        _n2w_cache[key] = word
        return word

    def _repl_clock_num(self, m: re.Match, lang_lc, is_num2words_compat, tts_engine, lang, lang_iso1) -> str:
        lc = language_clock.get(lang_lc) if 'language_clock' in globals() else None
        # Parse hh[:mm[:ss]]
        try:
            h = int(m.group(1))
            mnt = int(m.group(2))
            sec = m.group(3)
            sec = int(sec) if sec is not None else None
        except Exception:
            return m.group(0)
        # basic validation; if out of range, keep original
        if not (0 <= h <= 23 and 0 <= mnt <= 59 and (sec is None or 0 <= sec <= 59)):
            return m.group(0)
        # If no language clock rules, just say numbers plainly
        if not lc:
            parts = [self._n2w(h, lang_lc, is_num2words_compat, tts_engine, lang, lang_iso1)]
            if mnt != 0:
                parts.append(self._n2w(mnt, lang_lc, is_num2words_compat, tts_engine, lang, lang_iso1))
            if sec is not None and sec > 0:
                parts.append(self._n2w(sec, lang_lc, is_num2words_compat, tts_engine, lang, lang_iso1))
            return " ".join(parts)

        next_hour = (h + 1) % 24
        special_hours = lc.get("special_hours", {})
        # Build main phrase
        if mnt == 0 and (sec is None or sec == 0):
            if h in special_hours:
                phrase = special_hours[h]
            else:
                phrase = lc["oclock"].format(hour=self._n2w(h, lang_lc, is_num2words_compat, tts_engine, lang, lang_iso1))
        elif mnt == 15:
            phrase = lc["quarter_past"].format(hour=self._n2w(h, lang_lc, is_num2words_compat, tts_engine, lang, lang_iso1))
        elif mnt == 30:
            # German "halb drei" (= 2:30) uses next hour
            if lang_lc == "deu":
                phrase = lc["half_past"].format(next_hour=self._n2w(next_hour, lang_lc, is_num2words_compat, tts_engine, lang, lang_iso1))
            else:
                phrase = lc["half_past"].format(hour=self._n2w(h, lang_lc, is_num2words_compat, tts_engine, lang, lang_iso1))
        elif mnt == 45:
            phrase = lc["quarter_to"].format(next_hour=self._n2w(next_hour, lang_lc, is_num2words_compat, tts_engine, lang, lang_iso1))
        elif mnt < 30:
            phrase = lc["past"].format(hour=self._n2w(h, lang_lc, is_num2words_compat, tts_engine, lang, lang_iso1), minute=self._n2w(mnt, lang_lc, is_num2words_compat, tts_engine, lang, lang_iso1)) if mnt != 0 else lc["oclock"].format(hour=self._n2w(h, lang_lc, is_num2words_compat, tts_engine, lang, lang_iso1))
        else:
            minute_to_hour = 60 - mnt
            phrase = lc["to"].format(next_hour=self._n2w(next_hour, lang_lc, is_num2words_compat, tts_engine, lang, lang_iso1), minute=self._n2w(minute_to_hour, lang_lc, is_num2words_compat, tts_engine, lang, lang_iso1))
        # Append seconds if present
        if sec is not None and sec > 0:
            second_phrase = lc["second"].format(second=self._n2w(sec, lang_lc, is_num2words_compat, tts_engine, lang, lang_iso1))
            phrase = lc["full"].format(phrase=phrase, second_phrase=second_phrase)
        return phrase

    def _normalize_commas(self, num_str: str) -> str:
        """Normalize number string to standard comma format: 1,234,567"""
        tok = num_str.replace('\u00A0', '').replace(' ', '')
        if '.' in tok:
            integer_part, decimal_part = tok.split('.', 1)
            integer_part = integer_part.replace(',', '')
            integer_part = "{:,}".format(int(integer_part))
            return f"{integer_part}.{decimal_part}"
        else:
            integer_part = tok.replace(',', '')
            return "{:,}".format(int(integer_part))

    def _clean_single_num(self, num_str, lang, lang_iso1, is_num2words_compat):
        max_single_value: int = 999_999_999_999_999_999
        tok = unicodedata.normalize('NFKC', num_str)
        if tok.lower() in ('inf', 'infinity', 'nan'):
            return tok
        clean = tok.replace(',', '').replace('\u00A0', '').replace(' ', '')
        try:
            num = float(clean) if '.' in clean else int(clean)
        except (ValueError, OverflowError):
            return tok
        if not math.isfinite(num) or abs(num) > max_single_value:
            return tok

        # Normalize commas before final output
        tok = self._normalize_commas(tok)

        if is_num2words_compat:
            new_lang_iso1 = lang_iso1.replace('zh', 'zh_CN')
            return num2words(num, lang=new_lang_iso1)
        else:
            phoneme_map = language_math_phonemes.get(
                lang,
                language_math_phonemes.get(default_language_code, language_math_phonemes['eng'])
            )
            return ' '.join(phoneme_map.get(ch, ch) for ch in str(num))

    def _clean_formatted_number_match(self, match, lang, lang_iso1, is_num2words_compat):
        first_num = self._clean_single_num(match.group(1), lang, lang_iso1, is_num2words_compat)
        dash_char = match.group(2) or ''
        second_num = self._clean_single_num(match.group(3), lang, lang_iso1, is_num2words_compat) if match.group(3) else ''
        trailing = match.group(4) or ''
        if second_num:
            return f"{first_num}{dash_char}{second_num}{trailing}"
        else:
            return f"{first_num}{trailing}"

    def _repl_ambiguous(self, match, ambiguous_replacements):
        # handles "num SYMBOL num" and "SYMBOL num"
        if match.group(2) and match.group(2) in ambiguous_replacements:
            return f"{match.group(1)} {ambiguous_replacements[match.group(2)]} {match.group(3)}"
        if match.group(3) and match.group(3) in ambiguous_replacements:
            return f"{ambiguous_replacements[match.group(3)]} {match.group(4)}"
        return match.group(0)

    def __ordinal_to_words(self, m, lang_iso1, is_num2words_compat):
        n = int(m.group(1))
        if is_num2words_compat:
            try:
                from num2words import num2words
                return num2words(n, to="ordinal", lang=(lang_iso1 or "en"))
            except Exception:
                pass
        # If num2words isn't available/compatible, keep original token as-is.
        return m.group(0)

    def _is_valid_roman(self, s):
        valid_roman = re.compile(
            r'^(?=.)M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$',
            re.IGNORECASE
        )
        return bool(valid_roman.fullmatch(s))

    def _roman_to_int(self, s):
        s = s.upper()
        i, result = 0, 0
        while i < len(s):
            for roman, value in roman_numbers_tuples:
                if s[i:i+len(roman)] == roman:
                    result += value
                    i += len(roman)
                    break
            else:
                return s  # Not even a sequence of roman letters
        return result

    def _repl_roman_heading(self, m):
        roman = m.group(1)
        if not self._is_valid_roman(roman):
            return m.group(0)
        val = self._roman_to_int(roman)
        return f"{val}{m.group(2)}{m.group(3)}"

    def _repl_roman_standalone(self, m):
        roman = m.group(1)
        if not self._is_valid_roman(roman):
            return m.group(0)
        val = self._roman_to_int(roman)
        return f"{val}{m.group(2)}"

    def _repl_roman_word(self, m):
        roman = m.group(1)
        if not self._is_valid_roman(roman):
            return m.group(0)
        val = self._roman_to_int(roman)
        return str(val)

    def get_sentences(self, text, lang, tts_engine):
        """
        Splits a given text into a list of sentences based on language-specific rules
        and TTS engine character limits.

        This function is crucial for preparing text for TTS processing by breaking it
        down into manageable chunks that respect punctuation, special markup (SML),
        and character length constraints.

        Args:
            text (str): The input text to be segmented.
            lang (str): The language code (e.g., 'eng', 'fra') which determines
                        the max character limits and tokenization rules.
            tts_engine: The TTS engine identifier (currently unused in this method but
                        kept for API consistency).

        Returns:
            list: A list of strings, where each string is a sentence or a segment
                  of text suitable for TTS processing. Returns None if an error occurs.
        """
        try:
            # Set the maximum character limit for a sentence, leaving a small buffer.
            max_chars = language_mapping[lang]['max_chars'] - 4
            min_tokens = 5  # Minimum number of tokens for certain operations (currently unused).

            # 1. Initial Split by SML tokens (e.g., for breaks and pauses)
            # This ensures that special TTS markup tags are preserved as separate items.
            sml_list = re.split(rf"({'|'.join(map(re.escape, self.sml_tokens))})", text)
            sml_list = [s for s in sml_list if s.strip() or s in self.sml_tokens]

            # 2. Hard Split: Break text at major sentence-ending punctuation.
            # This uses a predefined set of "hard" punctuation marks (e.g., '.', '!', '?').
            pattern_split = '|'.join(map(re.escape, punctuation_split_hard_set))
            pattern = re.compile(rf"(.*?(?:{pattern_split}){''.join(punctuation_list_set)})(?=\s|$)", re.DOTALL)
            hard_list = []
            for s in sml_list:
                # Preserve SML tokens and short segments that are already under the character limit.
                if s in [TTS_SML['break'], TTS_SML['pause']] or len(s) <= max_chars:
                    hard_list.append(s)
                else:
                    # Use a custom split function to keep the delimiters.
                    parts = self._split_inclusive(s, pattern)
                    if parts:
                        for text_part in parts:
                            text_part = text_part.strip()
                            if text_part:
                                hard_list.append(text_part)
                    else:
                        s = s.strip()
                        if s:
                            hard_list.append(s)

            # 3. Soft Split: Further break down long sentences using "soft" punctuation.
            # This handles cases where a sentence is too long for the TTS engine,
            # using commas, semicolons, etc., as breaking points.
            pattern_split = '|'.join(map(re.escape, punctuation_split_soft_set))
            pattern = re.compile(rf"(.*?(?:{pattern_split}))(?=\s|$)", re.DOTALL)
            soft_list = []
            for s in hard_list:
                # Keep SML tokens and segments that are already compliant with the length limit.
                if s in [TTS_SML['break'], TTS_SML['pause']] or len(s) <= max_chars:
                    soft_list.append(s)
                # If a segment is still too long, apply the soft split.
                elif len(s) > max_chars:
                    parts = [p for p in self._split_inclusive(s, pattern) if p]
                    if parts:
                        buffer = ''
                        for idx, part in enumerate(parts):
                            # Predict the length if the next part is added to the buffer.
                            predicted_length = len(buffer) + (1 if buffer else 0) + len(part)
                            # If it fits, add it to the buffer.
                            if predicted_length <= max_chars:
                                buffer = (buffer + ' ' + part).strip() if buffer else part
                            else:
                                # If it doesn't fit, handle the buffer.
                                # Check if the buffer ends with soft punctuation.
                                if buffer and not any(buffer.rstrip().endswith(p) for p in punctuation_split_soft_set):
                                    # If not, try to backtrack to the last punctuation inside the buffer.
                                    last_punct_idx = max((buffer.rfind(p) for p in punctuation_split_soft_set if p in buffer), default=-1)
                                    if last_punct_idx != -1:
                                        # Split at the last found punctuation mark.
                                        soft_list.append(buffer[:last_punct_idx+1].strip())
                                        leftover = buffer[last_punct_idx+1:].strip()
                                        buffer = leftover + ' ' + part if leftover else part
                                    else:
                                        # If no punctuation, split as is.
                                        soft_list.append(buffer.strip())
                                        buffer = part
                                else:
                                    soft_list.append(buffer.strip())
                                    buffer = part
                        # Add any remaining text in the buffer to the list.
                        if buffer:
                            cleaned = re.sub(r'[^\p{L}\p{N} ]+', '', buffer)
                            if any(ch.isalnum() for ch in cleaned):
                                soft_list.append(buffer.strip())
                    else:
                        # If no soft punctuation is found, add the long segment as is.
                        cleaned = re.sub(r'[^\p{L}\p{N} ]+', '', s)
                        if any(ch.isalnum() for ch in cleaned):
                            soft_list.append(s.strip())
                else:
                    # Add segments that are within the length limit.
                    cleaned = re.sub(r'[^\p{L}\p{N} ]+', '', s)
                    if any(ch.isalnum() for ch in cleaned):
                        soft_list.append(s.strip())

            # 4. Language-specific processing for ideogram-based languages.
            # These languages require word tokenization before joining into sentences.
            if lang in ['zho', 'jpn', 'kor', 'tha', 'lao', 'mya', 'khm']:
                result = []
                for s in soft_list:
                    if s in [TTS_SML['break'], TTS_SML['pause']]:
                        result.append(s)
                    else:
                        # Segment the text into words/tokens.
                        tokens = self._segment_ideogramms(s, lang)
                        if isinstance(tokens, list):
                            result.extend([t for t in tokens if t.strip()])
                        else:
                            tokens = tokens.strip()
                            if tokens:
                                result.append(tokens)
                # Join the tokens back into sentences that respect the max character limit.
                return list(self._join_ideogramms(result, max_chars))
            else:
                # 5. Final segmentation for space-delimited languages.
                # This step ensures that no sentence exceeds the max character limit by splitting
                # at the word level if necessary.
                sentences = []
                for s in soft_list:
                    if s in [TTS_SML['break'], TTS_SML['pause']] or len(s) <= max_chars:
                        sentences.append(s)
                    else:
                        # Split by space and reconstruct sentences within the character limit.
                        words = s.split(' ')
                        text_part = words[0]
                        for w in words[1:]:
                            if len(text_part) + 1 + len(w) <= max_chars:
                                text_part += ' ' + w
                            else:
                                text_part = text_part.strip()
                                if text_part:
                                    sentences.append(text_part)
                                text_part = w
                        # Add the last remaining part of the sentence.
                        if text_part:
                            cleaned = re.sub(r'[^\p{L}\p{N} ]+', '', text_part).strip()
                            if not any(ch.isalnum() for ch in cleaned):
                                continue
                            sentences.append(text_part)
                return sentences
        except Exception as e:
            error = f'get_sentences() error: {e}'
            print(error)
            return None

    def _get_date_entities(self, text, stanza_nlp):
        try:
            doc = stanza_nlp(text)
            date_spans = []
            for ent in doc.ents:
                if ent.type == 'DATE':
                    date_spans.append((ent.start_char, ent.end_char, ent.text))
            return date_spans
        except Exception as e:
            error = f'get_date_entities() error: {e}'
            print(error)
            return False

    def _get_num2words_compat(self, lang_iso1):
        try:
            test = num2words(1, lang=lang_iso1.replace('zh', 'zh_CN'))
            return True
        except NotImplementedError:
            return False
        except Exception:
            return False

    def _set_formatted_number(self, text: str, lang, lang_iso1: str, is_num2words_compat: bool, max_single_value: int = 999_999_999_999_999_999):
        # match up to 18 digits, optional �,�� groups (allowing spaces or NBSP after comma), optional decimal of up to 12 digits
        # handle optional range with dash/en dash/em dash between numbers, and allow trailing punctuation
        number_re = re.compile(
            r'(?<!\w)'
            r'(\d{1,18}(?:,\s*\d{1,18})*(?:\.\d{1,12})?)'      # first number
            r'(?:\s*([-��])\s*'                                # dash type
            r'(\d{1,18}(?:,\s*\d{1,18})*(?:\.\d{1,12})?))?'    # optional second number
            r'([^\w\s]*)',                                     # optional trailing punctuation
            re.UNICODE
        )

        return number_re.sub(lambda m: self._clean_formatted_number_match(m, lang, lang_iso1, is_num2words_compat), text)

    def _year2words(self, year_str, lang, lang_iso1, is_num2words_compat):
        try:
            year = int(year_str)
            first_two = int(year_str[:2])
            last_two = int(year_str[2:])
            lang_iso1 = lang_iso1 if lang in language_math_phonemes.keys() else default_language_code
            lang_iso1 = lang_iso1.replace('zh', 'zh_CN')
            if not year_str.isdigit() or len(year_str) != 4 or last_two < 10:
                if is_num2words_compat:
                    return num2words(year, lang=lang_iso1)
                else:
                    return ' '.join(language_math_phonemes[lang].get(ch, ch) for ch in year_str)
            if is_num2words_compat:
                return f"{num2words(first_two, lang=lang_iso1)} {num2words(last_two, lang=lang_iso1)}" 
            else:
                return ' '.join(language_math_phonemes[lang].get(ch, ch) for ch in first_two) + ' ' + ' '.join(language_math_phonemes[lang].get(ch, ch) for ch in last_two)
        except Exception as e:
            error = f'year2words() error: {e}'
            print(error)
            raise
            return False

    def _clock2words(self, text, lang, lang_iso1, tts_engine, is_num2words_compat):
        time_rx = re.compile(r'(\d{1,2})[:.](\d{1,2})(?:[:.](\d{1,2}))?')
        lang_lc = (lang or "").lower()
        return time_rx.sub(lambda m: self._repl_clock_num(m, lang_lc, is_num2words_compat, tts_engine, lang, lang_iso1), text)

    def _math2words(self, text, lang, lang_iso1, tts_engine, is_num2words_compat):
        # Matches any digits + optional space/NBSP + st/nd/rd/th, not glued into words.
        re_ordinal = re.compile(r'(?<!\w)(\d+)(?:\s|\u00A0)*(?:st|nd|rd|th)(?!\w)')
        text = re.sub(r'(\d)\)', r'\1 : ', text)
        text = re_ordinal.sub(lambda m: self.__ordinal_to_words(m, lang_iso1, is_num2words_compat), text)
        # Symbol phonemes
        ambiguous_symbols = {"-", "/", "*", "x"}
        phonemes_list = language_math_phonemes.get(lang, language_math_phonemes[default_language_code])
        replacements = {k: v for k, v in phonemes_list.items() if not k.isdigit() and k not in [',', '.']}
        normal_replacements  = {k: v for k, v in replacements.items() if k not in ambiguous_symbols}
        ambiguous_replacements = {k: v for k, v in replacements.items() if k in ambiguous_symbols}
        # Replace unambiguous symbols everywhere
        if normal_replacements:
            sym_pat = r'(' + '|'.join(map(re.escape, normal_replacements.keys())) + r')'
            text = re.sub(sym_pat, lambda m: f" {normal_replacements[m.group(1)]} ", text)
        # Replace ambiguous symbols only in valid equation contexts
        if ambiguous_replacements:
            ambiguous_pattern = (
                r'(?<!\S)'                   # no non-space before
                r'(\d+)\s*([-/*x])\s*(\d+)'  # num SYMBOL num
                r'(?!\S)'                    # no non-space after
                r'|'                         # or
                r'(?<!\S)([-/*x])\s*(\d+)(?!\S)'  # SYMBOL num
            )
            text = re.sub(ambiguous_pattern, lambda m: self._repl_ambiguous(m, ambiguous_replacements), text)
        text = self._set_formatted_number(text, lang, lang_iso1, is_num2words_compat)
        return text

    def _roman2number(self, text):
        # Your heading/standalone rules stay
        text = re.sub(r'^(?:\s*)([IVXLCDM]+)([.-])(\s+)', self._repl_roman_heading, text, flags=re.MULTILINE)
        text = re.sub(r'^(?:\s*)([IVXLCDM]+)([.-])(?:\s*)$', self._repl_roman_standalone, text, flags=re.MULTILINE)

        # NEW: only convert whitespace-delimited tokens of length >= 2
        # This avoids: 19C, 19�C, �C, AC/DC, CD-ROM, single-letter "I"
        text = re.sub(r'(?<!\S)([IVXLCDM]{2,})(?!\S)', self._repl_roman_word, text)

        return text

    def _filter_sml(self, text):
        for key, value in TTS_SML.items():
            pattern = re.escape(key) if key == '###' else r'\[' + re.escape(key) + r'\]'
            text = re.sub(pattern, f" {value} ", text)
        return text

    def normalize_text(self, text, lang):
        # Remove emojis
        emoji_pattern = re.compile(f"[{''.join(emojis_list)}]+", flags=re.UNICODE)
        emoji_pattern.sub('', text)
        if lang in abbreviations_mapping:
            mapping = abbreviations_mapping[lang]
            # Sort keys by descending length so longer ones match first
            keys = sorted(mapping.keys(), key=len, reverse=True)
            # Build a regex that only matches whole �words� (tokens) exactly
            pattern = re.compile(
                r'(?<!\w)(' + '|'.join(re.escape(k) for k in keys) + r')(?!\w)',
                flags=re.IGNORECASE
            )
            text = pattern.sub(lambda m: self._repl_abbreviations(m, mapping), text)
        # This regex matches sequences like a., c.i.a., f.d.a., m.c., etc...
        pattern = re.compile(r'\b(?:[a-zA-Z]\.){1,}[a-zA-Z]?\b\.?')
        # uppercase acronyms
        text = re.sub(r'\b(?:[a-zA-Z]\.){1,}[a-zA-Z]?\b\.?', lambda m: m.group().replace('.', '').upper(), text)
        # Prepare SML tags
        text = self._filter_sml(text)
        # Replace multiple newlines ("\n\n", "\r\r", "\n\r", etc.) with a �pause� 1.4sec
        pattern = r'(?:\r\n|\r|\n){2,}'
        text = re.sub(pattern, f" {TTS_SML['pause']} ", text)
        # Replace single newlines ("\n" or "\r") with spaces
        text = re.sub(r'\r\n|\r|\n', ' ', text)
        # Replace punctuations causing hallucinations
        pattern = f"[{''.join(map(re.escape, punctuation_switch.keys()))}]"
        text = re.sub(pattern, lambda match: punctuation_switch.get(match.group(), match.group()), text)
        # Replace NBSP with a normal space
        text = text.replace("\xa0", " ")
        # Replace multiple and spaces with single space
        text = re.sub(r'\s+', ' ', text)
        # Replace ok by 'Owkey'
        text = re.sub(r'\bok\b', 'Okay', text, flags=re.IGNORECASE)
        # Replace parentheses with double quotes
        text = re.sub(r'\(([^)]+)\)', r'"\1"', text)
        # Escape special characters in the punctuation list for regex
        pattern = '|'.join(map(re.escape, punctuation_split_hard_set))
        # Reduce multiple consecutive punctuations
        text = re.sub(rf'(\s*({pattern})\s*)+', r'\2 ', text).strip()
        # Escape special characters in the punctuation list for regex
        pattern = '|'.join(map(re.escape, punctuation_split_soft_set))
        # Reduce multiple consecutive punctuations
        text = re.sub(rf'(\s*({pattern})\s*)+', r'\2 ', text).strip()
        # Pattern 1: Add a space between UTF-8 characters and numbers
        text = re.sub(r'(?<=[\p{L}])(?=\d)|(?<=\d)(?=[\p{L}])', ' ', text)
        # Replace special chars with words
        specialchars = specialchars_mapping.get(lang, specialchars_mapping.get(default_language_code, specialchars_mapping['eng']))
        specialchars_table = {ord(char): f" {word} " for char, word in specialchars.items()}
        text = text.translate(specialchars_table)
        text = ' '.join(text.split())
        return text

    def convert_chapters2audio(self, session):
        """
        Converts text chapters into audio files using a TTS engine.

        This method orchestrates the text-to-speech conversion process. It manages
        the TTS engine, handles resuming from a previously interrupted session,
        iterates through chapters and sentences, generates audio for each sentence,
        and then combines the sentence audio files into a single file for each chapter.

        Args:
            session (dict): A dictionary containing all session-related data, including:
                - 'cancellation_requested' (bool): Flag to stop the process.
                - 'tts_engine' (str): The identifier for the TTS engine to use.
                - 'chapters_dir' (str): Path to the directory for storing chapter audio.
                - 'chapters_dir_sentences' (str): Path to the directory for storing sentence audio.
                - 'chapters' (list): A list of chapters, where each chapter is a list of sentences.

        Returns:
            bool: True if the conversion is successful, False otherwise.
        """
        ebook_audio = EbookAudio()
        try:
            # Immediately exit if a cancellation request has been detected.
            if session['cancellation_requested']:
                print('Cancel requested')
                return False

            # Initialize the TTS manager with the current session configuration.
            tts_manager = TTSManager(session)
            if not tts_manager:
                error = f"TTS engine {session['tts_engine']} could not be loaded!\nPossible reason can be not enough VRAM/RAM memory.\nTry to lower max_tts_in_memory in ./lib/models.py"
                print(error)
                return False

            # --- Resume Logic ---
            # Determine the starting point if resuming a previous session.
            resume_chapter = 0
            missing_chapters = []
            resume_sentence = 0
            missing_sentences = []

            # Check for already processed chapter audio files to find the resume point.
            existing_chapters = sorted(
                [f for f in os.listdir(session['chapters_dir']) if f.endswith(f'.{default_audio_proc_format}')],
                key=lambda x: int(re.search(r'\d+', x).group())
            )
            if existing_chapters:
                # Find the last successfully created chapter.
                resume_chapter = max(int(re.search(r'\d+', f).group()) for f in existing_chapters)
                print(f'Resuming from chapter {resume_chapter}')
                # Identify any chapters that are missing before the resume point.
                existing_chapter_numbers = {int(re.search(r'\d+', f).group()) for f in existing_chapters}
                missing_chapters = [i for i in range(1, resume_chapter) if i not in existing_chapter_numbers]
                if resume_chapter not in missing_chapters:
                    missing_chapters.append(resume_chapter)

            # Check for already processed sentence audio files.
            existing_sentences = sorted(
                [f for f in os.listdir(session['chapters_dir_sentences']) if f.endswith(f'.{default_audio_proc_format}')],
                key=lambda x: int(re.search(r'\d+', x).group())
            )
            if existing_sentences:
                # Find the last successfully created sentence.
                resume_sentence = max(int(re.search(r'\d+', f).group()) for f in existing_sentences)
                print(f"Resuming from sentence {resume_sentence}")
                # Identify any sentences that are missing before the resume point.
                existing_sentence_numbers = {int(re.search(r'\d+', f).group()) for f in existing_sentences}
                missing_sentences = [i for i in range(1, resume_sentence) if i not in existing_sentence_numbers]
                if resume_sentence not in missing_sentences:
                    missing_sentences.append(resume_sentence)

            # --- Process Initialization ---
            total_chapters = len(session['chapters'])
            if total_chapters == 0:
                print('No chapters found!')
                return False

            # Calculate total number of items (sentences + SML tokens) for the progress bar.
            total_iterations = sum(len(session['chapters'][x]) for x in range(total_chapters))
            # Calculate the total number of actual sentences to be converted.
            total_sentences = sum(sum(1 for row in chapter if row.strip() not in TTS_SML.values()) for chapter in session['chapters'])
            if total_sentences == 0:
                print('No sentences found!')
                return False

            sentence_number = 0
            print(f"--------------------------------------------------\nA total of {total_chapters} {'chapter' if total_chapters <= 1 else 'chapters'} and {total_sentences} {'sentence' if total_sentences <= 1 else 'sentences'}.\n--------------------------------------------------")

            # --- Main Processing Loop ---
            progress_bar = gr.Progress(track_tqdm=False)
            with tqdm(total=total_iterations, desc='0.00%', bar_format='{desc}: {n_fmt}/{total_fmt} ', unit='step', initial=0) as t:
                for x in range(total_chapters):
                    chapter_num = x + 1
                    chapter_audio_file = f'chapter_{chapter_num}.{default_audio_proc_format}'
                    sentences = session['chapters'][x]
                    sentences_count = sum(1 for row in sentences if row.strip() not in TTS_SML.values())
                    start = sentence_number  # Mark the starting sentence number for this chapter.
                    print(f'Chapter {chapter_num} containing {sentences_count} sentences...')

                    # Iterate through each sentence/SML token in the chapter.
                    for i, sentence in enumerate(sentences):
                        if session['cancellation_requested']:
                            print('Cancel requested')
                            return False

                        # Determine if the sentence needs to be processed.
                        # This is true if it's a missing sentence, or if it's beyond the last processed sentence.
                        if sentence_number in missing_sentences or sentence_number > resume_sentence or (sentence_number == 0 and resume_sentence == 0):
                            if sentence_number <= resume_sentence and sentence_number > 0:
                                print(f'**Recovering missing file sentence {sentence_number}')
                            
                            sentence = sentence.strip()
                            # Convert sentence to audio. SML tokens are skipped but still marked as success.
                            success = tts_manager.convert_sentence2audio(sentence_number, sentence) if sentence else True
                            if success:
                                # Update progress bar and console output.
                                total_progress = (t.n + 1) / total_iterations
                                progress_bar(total_progress)
                                is_sentence = sentence.strip() not in TTS_SML.values()
                                percentage = total_progress * 100
                                t.set_description(f'{percentage:.2f}%')
                                print(f" | {sentence}")
                            else:
                                # If TTS fails for any sentence, abort the entire process.
                                return False

                        # Increment sentence number only for actual sentences, not SML tokens.
                        if sentence.strip() not in TTS_SML.values():
                            sentence_number += 1
                        
                        t.update(1)  # Advance progress bar for every item (sentence or SML).

                    # --- Chapter Finalization ---
                    # Mark the ending sentence number for this chapter.
                    end = sentence_number - 1 if sentence_number > 1 else sentence_number
                    print(f"End of chapter {chapter_num}")

                    # Combine the generated sentence audio files into a single chapter file.
                    # This is done if the chapter was missing or is new.
                    if chapter_num in missing_chapters or sentence_number > resume_sentence:
                        if chapter_num <= resume_chapter:
                            print(f'**Recovering missing file chapter {chapter_num}')
                        
                        if ebook_audio.combine_audio_sentences(chapter_audio_file, start, end, session):
                            print(f'Combining chapter {chapter_num} to audio, sentence {start} to {end}')
                        else:
                            print('combine_audio_sentences() failed!')
                            return False
            return True
        except Exception as e:
            DependencyError(e)
            return False
