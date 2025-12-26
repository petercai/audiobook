import io
import os
import shutil
import subprocess
import stanza
import ebooklib
import gradio as gr
import pymupdf4llm
import regex as re
from PIL import Image
from bs4 import BeautifulSoup, NavigableString, Tag
from tqdm import tqdm

from lib.classes.tts_manager import TTSManager
from lib.conf import default_audio_proc_format, ebook_formats, models_dir
from lib.ebook_audio import EbookAudio
from lib.functions import DependencyError
from lib.lang import language_mapping, year_to_decades_languages
from lib.models import TOKENIZER_FREE_TTS, TTS_SML
from lib.text_normalizer import TextNormalizer

is_gui_process = False

class EPubProcessor:

    def __init__(self):
        self.ebook_audio = EbookAudio()
        self.text_normalizer = TextNormalizer()
        self.heading_tags = {"h1", "h2", "h3", "h4", "h5", "h6"}
        self.break_tags = {"p", "div", "li", "br", "hr"}
        self.pause_tags = {"ol", "ul"}
        self.proc_tags = {
            "p", "div", "span", "a", "li", "ol", "ul", "i", "b", "em",
            "strong", "blockquote", "q", "cite", "code", "pre", "br", "hr"
        } | self.heading_tags | self.break_tags | self.pause_tags

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
                return None
            cover_image = None
            cover_path = os.path.join(session['process_dir'], session['filename_noext'] + '.jpg')
            cover_items = epubBook.get_items_of_type(ebooklib.ITEM_COVER)
            for item in cover_items:
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
            return None
        except Exception as e:
            DependencyError(e)
            return None

    def get_chapters_in_sentences(self, epubBook, session):
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

            toc_epub_docs = self.map_filter_chapters_to_toc(all_docs, toc)

            # If chapters_to_process is specified, limit the documents and TOC to be processed
            # if chapters_to_process > 0:
            #     all_docs = all_docs[:chapters_to_process]
                
            # Attempt to extract the book title for metadata
            ebook_title = self.get_ebook_title(epubBook, all_docs)

            stanza_nlp = self.init_stanza_nlp(language_iso_, session)

            # Check if the num2words library supports the current language
            # This determines how numbers will be converted to words
            is_num2words_compat = TextNormalizer.get_num2words_compat(language_iso_)
            
            # Inform user that numerical and mathematical content analysis is beginning
            msg = 'Analyzing numbers, maths signs, dates and time to convert in words...'
            print(msg)

            # Initialize the chapters list to store processed content
            # todo: toc and chapter should be a list of dicts
            chapters = []
            pending_sentences = []
            toc_items = list(toc) if isinstance(toc, (list, tuple)) else None
            # merged_toc = [] if toc_items is not None else toc

            # Process each document (chapter) in the EPUB
            # The loop will iterate through all documents or a limited number if chapters_to_process is set
            for title, chapter_doc in toc_epub_docs.items():
                # Process the chapter content with various text transformations
                # This includes number conversion, punctuation handling, and sentence segmentation
                chapter_sentences = self.filter_chapter(
                    chapter_doc,
                    language_, 
                    language_iso_, 
                    tts_engine_, 
                    stanza_nlp, 
                    is_num2words_compat
                )
                
                # Handle the result of chapter processing
                if chapter_sentences is None:
                    # If processing failed, stop further processing
                    break
                elif len(chapter_sentences) > 0:
                    if len(chapter_sentences) < 3:
                        pending_sentences.extend(chapter_sentences)
                        continue
                    if pending_sentences:
                        chapter_sentences = pending_sentences + chapter_sentences
                        pending_sentences = []
                    # If successfully processed and contains content, add to chapters
                    chapters.append(chapter_sentences)


            if pending_sentences:
                if chapters:
                    chapters[-1].extend(pending_sentences)
                else:
                    chapters.append(pending_sentences)


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

    def init_stanza_nlp(self, language_iso_, session):
        # Initialize Stanza NLP pipeline for languages that require advanced processing
        # This is used for date recognition and other NLP tasks
        stanza_nlp = None
        if language_iso_ in year_to_decades_languages:
            try:
                # Download the required language model if not already present
                stanza.download(language_iso_, model_dir=os.path.join(models_dir, 'stanza'), logging_level='WARN',
                                verbose=False if session['offline_mode'] else None)
            except Exception as e:
                if session['offline_mode']:
                    print(
                        f"Offline mode: Failed to find stanza model for '{language_iso_}'. Expected in '{os.path.join(models_dir, 'stanza')}'")
                raise e
            # Create a processing pipeline for tokenization and named entity recognition
            stanza_nlp = stanza.Pipeline(language_iso_, processors='tokenize,ner')
        return stanza_nlp

    def get_epub_chapters(self, epubBook, language_):
        try:
            toc = epubBook.toc  # Extract TOC
            toc_list = []
            for item in toc:
                if hasattr(item, 'title'):
                    normalized_title = self.text_normalizer.normalize_english_text(
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

    def map_filter_chapters_to_toc(self, all_docs, toc):
        doc_by_name = {}
        doc_by_basename = {}
        for doc in all_docs:
            doc_name = getattr(doc, "file_name", None) or getattr(doc, "href", None)
            if doc_name:
                doc_by_name[doc_name] = doc
                doc_by_basename[os.path.basename(doc_name)] = doc
        toc_docs = {}
        for item in self.toc_items_iter(toc):
            toc_title = getattr(item, "title", None)
            href = getattr(item, "href", None) or getattr(item, "file_name", None)
            if not (toc_title and href):
                continue
            href_base = href.split("#", 1)[0]
            doc = (
                doc_by_name.get(href)
                or doc_by_name.get(href_base)
                or doc_by_basename.get(os.path.basename(href_base))
            )
            if doc is not None:
                if not doc.title:
                    doc.title = toc_title
                toc_docs[toc_title] = doc
        return toc_docs

    def toc_items_iter(self, items):
        for item in items:
            if (
                isinstance(item, (list, tuple))
                and len(item) == 2
                and isinstance(item[1], (list, tuple))
            ):
                section, children = item
                yield section
                if children:
                    yield from self.toc_items_iter(children)
            else:
                yield item

    def _tuple_row_iterator(self, node, last_text_char=None, tokenizer_tts=True):
        """
        Recursively traverses a BeautifulSoup HTML node tree and yields structured content tuples.

        This generator function walks through the HTML elements of a chapter, extracting
        text, headings, and tables. It also identifies structural tags to insert
        special markup language (SML) tokens for breaks and pauses, which are used
        by certain TTS engines to produce more natural-sounding speech.

        Args:
            node (bs4.Tag or bs4.BeautifulSoup): The BeautifulSoup node to traverse.
            last_text_char (str, optional): The last character of the previously yielded
                text segment. This is used to make decisions about inserting break tokens.
                Defaults to None.
            tokenizer_tts (bool, optional): A flag indicating whether the TTS engine
                requires explicit SML tokens for pausing and sentence breaking. If True,
                the generator will yield 'break' and 'pause' tuples. This should be set
                based on whether the selected TTS engine is in the TOKENIZER_FREE_TTS list.
                Defaults to True.

        Yields:
            tuple: A tuple in the format (type, content), where 'type' can be one of
                   "text", "heading", "table", "break", or "pause", and 'content' is
                   the corresponding data (string, bs4.Tag, or SML token).
        """
        try:
            # Iterate over each child of the current HTML node.
            for child in node.children:
                # If the child is a text string (not a tag).
                if isinstance(child, NavigableString):
                    text = child.strip()
                    # Yield the text if it's not empty.
                    if text:
                        yield ("text", text)
                        # Update the last character seen to track context for break insertion.
                        last_text_char = text[-1] if text else last_text_char

                # If the child is an HTML tag.
                elif isinstance(child, Tag):
                    name = child.name.lower()
                    # Handle heading tags (h1, h2, etc.).
                    if name in self.heading_tags:
                        title = child.get_text(separator=' ', strip=True)
                        if title:
                            yield ("heading", title)
                            # Update the last character seen.
                            last_text_char = title[-1] if title else last_text_char

                    # Handle table tags. The table content will be processed later.
                    elif name == "table":
                        yield ("table", child)

                    # Handle other tags that are part of the processable set.
                    else:
                        return_data = False
                        # Check if the tag is one we should process for content (e.g., p, div, span).
                        if name in self.proc_tags:
                            # Recursively call this function on the child tag's content.
                            for inner in self._tuple_row_iterator(child, last_text_char, tokenizer_tts):
                                return_data = True
                                yield inner
                                # Track the last character from any yielded text or heading.
                                if inner[0] in ("text", "heading") and inner[1]:
                                    last_text_char = inner[1][-1]

                            # After processing a tag's content, decide if a break or pause is needed.
                            if return_data:
                                # If it's a block-level tag that implies a break (e.g., <p>, <div>).
                                if name in self.break_tags:
                                    # Yield a break token if the TTS needs it and the preceding text
                                    # ends with punctuation (or if there was no preceding text).
                                    # This preserves structural breaks that coincide with sentence ends.
                                    if tokenizer_tts and not (last_text_char and (last_text_char.isalnum() or last_text_char.isspace())):
                                        yield ("break", TTS_SML['break'])
                                # If the TTS needs it, yield a pause after headings or list containers for better pacing.
                                elif tokenizer_tts and name in self.heading_tags or name in self.pause_tags:
                                    yield ("pause", TTS_SML['pause'])

                        # If the tag is not in our processable set, just traverse into it
                        # without adding any special breaks or pauses for the tag itself.
                        else:
                            yield from self._tuple_row_iterator(child, last_text_char, tokenizer_tts)

        except Exception as e:
            error = f'filter_chapter() tuple_row() error: {e}'
            DependencyError(error)
            return None

    def filter_chapter(self, doc_chapter, lang, lang_iso1, tts_engine, stanza_nlp, is_num2words_compat):
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
            is_tokenizer_tts = tts_engine not in TOKENIZER_FREE_TTS
            tuples_structured_sentence_list = self._extract_chapter_structured_sentence_list(doc_chapter, is_tokenizer_tts)
            if not tuples_structured_sentence_list:
                return []
            # Get the maximum character limit for the current language to ensure proper sentence segmentation
            max_chars = language_mapping[lang]['max_chars'] - 4
            clean_list = self._to_flat_sentence_list_with_break(
                tuples_structured_sentence_list,
                is_tokenizer_tts,
                max_chars
            )
            # Join the cleaned list into a single text string for further processing
            text = ' '.join(clean_list)
            # If the text is empty or contains no valid characters, return None to indicate no content
            if not re.search(r"[^\W_]", text):
                error = 'No valid text found!'
                print(error)
                return None
            sentences = self.text_normalizer.normalize_text(text, lang, lang_iso1, tts_engine, stanza_nlp, is_num2words_compat)
            if len(sentences) == 0:
                error = 'No sentences found!'
                print(error)
                return None
            # Return the processed sentences for TTS conversion
            return sentences
        except Exception as e:
            error = f'filter_chapter() error: {e}'
            DependencyError(error)
            return None

    def _extract_chapter_structured_sentence_list(self, doc_chapter, is_tokenizer_tts):
        # Decode the HTML content of the chapter from the ebook document.
        raw_html = doc_chapter.get_content().decode("utf-8")
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
                epub_type = (section_tag.get("epub:type", "") or section_tag.get("epub_type", "") or "").lower()
            nav_tag = content_root.find("nav")
            if nav_tag:
                epub_type = (nav_tag.get("epub:type", "") or nav_tag.get("epub_type", "") or "").lower()
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
        return list(self._tuple_row_iterator(content_root, is_tokenizer_tts))

    def _to_flat_sentence_list_with_break(self, tuples_structured_sentence_list, is_tokenizer_tts, max_chars):
        # Process the structured list to build a flat list of text elements.
        text_list = []
        handled_tables = set()  # Keep track of tables we've already processed
        prev_typ = None  # Track the previous element type to avoid duplicate breaks/pauses
        for typ, payload in tuples_structured_sentence_list:
            if typ == "heading":
                # Add heading text to the list after stripping whitespace
                text_list.append(payload.strip())
            elif typ == "break":
                # Avoid adding multiple consecutive break tokens which could cause unwanted pauses
                if prev_typ != 'break' and is_tokenizer_tts:
                    text_list.append(TTS_SML['break'])
            elif typ == 'pause' and is_tokenizer_tts:
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
                        line = " - ".join(f"{h}: {c}" for h, c in zip(headers, cells))
                    else:
                        # Otherwise, just join the cells with separators
                        line = " - ".join(cells)
                    if line:
                        text_list.append(line.strip())
            else:
                # Handle regular text content
                text = payload.strip()
                if text:
                    text_list.append(text)
            prev_typ = typ
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
        return clean_list

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
