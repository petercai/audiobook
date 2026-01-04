import io
import os
import ebooklib
import regex as re
from PIL import Image
from bs4 import BeautifulSoup, NavigableString, Tag
from lib.ebook_audio import EbookAudio
from lib.models import TOKENIZER_FREE_TTS, TTS_SML, TTS_SML_CN
from lib.util import util
from syntrive.adapters.text.normalizer import TextNormalizer
from syntrive.adapters.text.sentence_splitter import SentenceSplitter

is_gui_process = False

class EPubProcessor:

    def __init__(self, session):
        self.lang = session.get('language_iso1', 'en')
        self.offline_mode =  session.get('offline_mode', False)
        self.heading_tags = {"h1", "h2", "h3", "h4", "h5", "h6"}
        self.break_tags = {"p", "div", "li", "br", "hr"}
        self.pause_tags = {"ol", "ul"}
        self.skip_tags = {"sup"}
        self.proc_tags = {
            "p", "div", "span", "a", "li", "ol", "ul", "i", "b", "em",
            "strong", "blockquote", "q", "cite", "code", "pre", "br", "hr"
        } | self.heading_tags | self.break_tags | self.pause_tags

    def get_ebook_title(self, epubBook, first_doc):
        # 1. Try metadata (official EPUB title)
        meta_title = epubBook.get_metadata("DC", "title")
        if meta_title and meta_title[0][0].strip():
            return meta_title[0][0].strip()
        # 2. Try <title> in the head of the first XHTML document
        if first_doc:
            html = first_doc.get_content().decode("utf-8")
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

    def extract_book_cover(self, epubBook, path, cover_name):        
        """
        Extracts the cover image from an EPUB book and saves it as a JPEG file.

        This method attempts to find the cover image within the EPUB book. It first
        looks for items explicitly marked as 'cover' by ebooklib. If no such item
        is found, it then searches for any image item whose filename or ID contains
        the word 'cover' (case-insensitive). If a cover image is found, it is converted
        to JPEG format (if necessary) and saved to the specified path.

        Args:
            epubBook (ebooklib.epub.EpubBook): The EpubBook object from which to extract the cover.
            path (str): The directory where the cover image should be saved.
            cover_name (str): The base filename (without extension) for the cover image.

        Returns:
            str or None: The absolute path to the saved cover image file if successful,
                         otherwise None (e.g., if no cover is found or cancellation is requested).
        """

        try:
            cover_image = None
            cover_path = os.path.join(path, cover_name + '.jpg')
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
            util.print_error(e)
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
            tts_engine_ = session['tts_engine']
            
            # Step 1: Extract TOC (Table of Contents) and document list
            # Get all documents in reading order and the table of contents
            all_docs, toc = self.get_epub_chapters(epubBook)
            if not all_docs:
                return [], []

            toc_epub_docs = self.filter_chapters_with_toc(all_docs, toc)

            # Attempt to extract the book title for metadata
            # ebook_title = self.get_ebook_title(epubBook, all_docs[0])
            is_add_toc_title_to_chapters = session.get('add_toc_title', False)

            # Inform user that numerical and mathematical content analysis is beginning
            msg = 'Analyzing numbers, maths signs, dates and time to convert in words...'
            print(msg)

            # Initialize the chapters list to store processed content
            processed_chapters = []
            pending_sentences = []
            self.text_normalizer = TextNormalizer(
                    self.lang,
                    offline_model=self.offline_mode
                )

            # Process each document (chapter) in the EPUB
            # The loop will iterate through all documents or a limited number if chapters_to_process is set
            for chapter_doc, title in toc_epub_docs.items():
                # Process the chapter content with various text transformations
                # This includes number conversion, punctuation handling, and sentence segmentation
                chapter_sentences = self.filter_chapter(
                    chapter_doc,
                    tts_engine_
                )
                # Handle the result of chapter processing
                if chapter_sentences is None:
                    # If not sentences were extracted, skip this chapter
                    continue
                elif len(chapter_sentences) > 0:
                    if len(chapter_sentences) < 3:
                        pending_sentences.extend(chapter_sentences)
                        continue
                    chapter_sentences = [title] + chapter_sentences if is_add_toc_title_to_chapters else chapter_sentences
                    if pending_sentences:
                        chapter_sentences = pending_sentences + chapter_sentences
                        pending_sentences = []
                    # If successfully processed and contains content, add to chapters
                    processed_chapters.append(chapter_sentences)

            if pending_sentences:
                if processed_chapters:
                    processed_chapters[-1].extend(pending_sentences)
                else:
                    processed_chapters.append(pending_sentences)


            # Verify that at least one chapter was successfully processed
            if len(processed_chapters) == 0:
                error = 'No chapters found!'
                return None, None
                
            # Return the table of contents and processed chapters
            return toc, processed_chapters
            
        except Exception as e:
            # Handle any unexpected errors during processing
            error = f'Error extracting main content pages: {e}'
            util.print_error(Exception(error))
            return None, None
    def get_epub_chapters(self, epubBook):
        try:
            toc = epubBook.toc  # Extract TOC
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

    def filter_chapters_with_toc(self, all_docs, toc):
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
                toc_docs[doc] = toc_title
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

    def _tagged_tuple_paragraphs_iterator(self, node, last_text_char=None, tokenizer_tts=True, lan_code='en'):
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
            heading_tracker = False
            pending_span_letter = None
            node_has_text = False
            # Iterate over each child of the current HTML node.
            for child in node.children:
                # If the child is a text string (not a tag).
                if isinstance(child, NavigableString):
                    raw_text = str(child)
                    text = raw_text.strip()
                    if pending_span_letter and raw_text and raw_text[0].isspace() and not text:
                        yield ("text", pending_span_letter)
                        last_text_char = pending_span_letter[-1]
                        node_has_text = True
                        pending_span_letter = None
                        continue
                    # Yield the text if it's not empty.
                    if text:
                        if pending_span_letter:
                            if raw_text and raw_text[0].isspace():
                                yield ("text", pending_span_letter)
                                last_text_char = pending_span_letter[-1]
                                node_has_text = True
                                pending_span_letter = None
                            elif text[0].isalpha():
                                text = pending_span_letter + text
                                pending_span_letter = None
                            else:
                                yield ("text", pending_span_letter)
                                last_text_char = pending_span_letter[-1]
                                node_has_text = True
                                pending_span_letter = None
                        yield ("text", text)
                        # Update the last character seen to track context for break insertion.
                        last_text_char = text[-1] if text else last_text_char
                        node_has_text = True

                # If the child is an HTML tag.
                elif isinstance(child, Tag):
                    name = child.name.lower()
                    if name in self.skip_tags:
                        continue
                    # Handle heading tags (h1, h2, etc.).
                    if name in self.heading_tags:
                        title = child.get_text(separator=' ', strip=True)
                        if not title:
                            title_attr = child.get("title")
                            if title_attr:
                                title = title_attr.strip()
                        if title:
                            heading_tracker = True # found heading tag
                            yield ("heading", title)
                            # Update the last character seen.
                            last_text_char = title[-1] if title else last_text_char
                            node_has_text = True

                    # Handle table tags. The table content will be processed later.
                    elif name == "table":
                        yield ("table", child)

                    # Handle other tags that are part of the processable set.
                    else:
                        return_data = False
                        # Check if the tag is one we should process for content (e.g., p, div, span).
                        if name in self.proc_tags:
                            if (
                                name == "span"
                                and lan_code == "en"
                                and not pending_span_letter
                            ):
                                span_text = child.get_text(strip=True)
                                is_sentence_start = last_text_char is None or last_text_char in ".!?"
                                if (
                                    span_text
                                    and len(span_text) == 1
                                    and span_text.isalpha()
                                    and (not node_has_text or is_sentence_start)
                                ):
                                    pending_span_letter = span_text
                                    return_data = True
                                    continue
                            # Recursively call this function on the child tag's content.
                            for inner in self._tagged_tuple_paragraphs_iterator(child, last_text_char, tokenizer_tts, lan_code):
                                if pending_span_letter:
                                    if inner[0] == "text" and inner[1] and inner[1][0].isalpha():
                                        inner = ("text", pending_span_letter + inner[1].lstrip())
                                        pending_span_letter = None
                                    else:
                                        yield ("text", pending_span_letter)
                                        last_text_char = pending_span_letter[-1]
                                        node_has_text = True
                                        pending_span_letter = None
                                return_data = True
                                yield inner
                                # Track the last character from any yielded text or heading.
                                if inner[0] in ("text", "heading") and inner[1]:
                                    last_text_char = inner[1][-1]
                                    node_has_text = True

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
                                elif tokenizer_tts and (name in self.heading_tags or name in self.pause_tags):
                                    yield ("pause", TTS_SML['pause'])

                        # If the tag is not in our processable set, just traverse into it
                        # without adding any special breaks or pauses for the tag itself.
                        else:
                            if pending_span_letter:
                                yield ("text", pending_span_letter)
                                last_text_char = pending_span_letter[-1]
                                node_has_text = True
                                pending_span_letter = None
                            yield from self._tagged_tuple_paragraphs_iterator(child, last_text_char, tokenizer_tts, lan_code)

            if pending_span_letter:
                yield ("text", pending_span_letter)
            if tokenizer_tts and heading_tracker:
                yield ("break", TTS_SML['break'])

        except Exception as e:
            error = f'filter_chapter() tuple_row() error: {e}'
            util.print_error(e, error)
            return None

    def filter_chapter(self, doc_chapter, tts_engine):
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
            lang_iso1: ISO 639-1 language code (e.g., 'en', 'fr')
            tts_engine: Text-to-speech engine identifier
        Returns:
            list: List of processed sentences ready for TTS conversion, or None if errors occur
        """
        try:
            is_tokenizer_tts = tts_engine not in TOKENIZER_FREE_TTS
            tagged_paragraph_list = self.extract_chapter_tagged_paragraphes(doc_chapter, is_tokenizer_tts)
            if not tagged_paragraph_list:
                return []
            
            # Get the maximum character limit for the current language to ensure proper sentence segmentation
            paragraph_list = self._flat_paragraphes_with_break(
                tagged_paragraph_list,
                is_tokenizer_tts,
            )
            sentences = []
            sentence_splitter = SentenceSplitter(self.lang)
            # Join the paragraph_list into a single text string for further processing
            merged_chapter = ' '.join(paragraph_list)          
            if self.lang == "zh":
                cn_sentences = sentence_splitter.split(merged_chapter, self.lang)
                for cn_sentence in cn_sentences:
                    normalized_text = self.text_normalizer.normalize_text_4_tts(cn_sentence, tts_engine)
                    sentences.append(normalized_text)
            else:
                normalized_text = self.text_normalizer.normalize_text_4_tts(merged_chapter, tts_engine)
                sentences = sentence_splitter.split(normalized_text, self.lang)

            
            if len(sentences) == 0:
                error = 'No sentences found!'
                print(error)
                return None
            # Return the processed sentences for TTS conversion
            return sentences
        except Exception as e:
            error = f'filter_chapter() error: {e}'
            util.print_error(e)
            return None

    def extract_chapter_tagged_paragraphes(self, doc_chapter, is_tokenizer_tts: bool) -> list[tuple[str, str]]:
        """
        Extracts structured paragraphs from an EPUB chapter document.

        This method parses the HTML content of an EPUB chapter, filters out
        non-content sections (like TOC, frontmatter), removes script and style tags,
        and then recursively traverses the remaining HTML to extract text, headings,
        and tables into a structured list of tuples. Each tuple indicates the type
        of content (e.g., "text", "heading", "table", "break", "pause") and its payload.

        Args:
            doc_chapter (ebooklib.epub.EpubItem): The ebooklib document object representing a chapter.
            is_tokenizer_tts (bool): A flag indicating whether the TTS engine requires
                                     explicit SML tokens for pausing and sentence breaking.

        Returns:
            list[tuple[str, str]]: A list of tuples, where each tuple is (type, content).
                                   'type' can be "text", "heading", "table", "break", or "pause".
                                   'content' is the corresponding string or BeautifulSoup Tag.
                                   Returns an empty list if the chapter is empty or an excluded type.
        """
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
        return list(self._tagged_tuple_paragraphs_iterator(
            content_root,
            tokenizer_tts=is_tokenizer_tts,
            lan_code=self.lang
        ))

    def _flat_paragraphes_with_break(self, tuples_tagged_paragraph_list: list[tuple[str, any]], is_tokenizer_tts: bool) -> list[str]:
        """
        Converts a structured list of paragraph tuples into a flat list of text elements,
        handling special markers for breaks and pauses, and processing tables.

        This method iterates through the `tuples_structured_paragraph_list` which contains
        elements like text, headings, breaks, pauses, and tables. It flattens these into
        a single list of strings, applying specific logic for each type:
        - "heading": Adds the heading text.
        - "break": Inserts a `TTS_SML['break']` token, avoiding consecutive breaks.
        - "pause": Inserts a `TTS_SML['pause']` token, avoiding consecutive pauses.
        - "table": Converts HTML table structures into a readable string format,
                   including headers and row data, and appends them to the list.
                   It also prevents duplicate processing of the same table.
        - "text": Adds the plain text content.

        If `is_tokenizer_tts` is True, it also calls `_clean_paragraph_text` to further
        process the list, merging short sentences that might have been artificially
        separated by break tokens, to improve speech flow.

        Args:
            tuples_structured_paragraph_list (list[tuple[str, Any]]): A list of tuples,
                where each tuple is (type, content). 'type' can be "text", "heading",
                "table", "break", or "pause". 'content' is the corresponding string
                or BeautifulSoup Tag for tables.
            is_tokenizer_tts (bool): A flag indicating whether the TTS engine requires
                explicit SML tokens for pausing and sentence breaking. If True, SML
                tokens are inserted and further cleaning is applied.

        Returns:
            list[str]: A flat list of strings, where each string is a segment of text
                       or an SML token, ready for further text normalization and TTS.
        """

        # Process the structured list to build a flat list of text elements.
        paragraph_text_list = []
        handled_tables = set()  # Keep track of tables we've already processed
        prev_typ = None  # Track the previous element type to avoid duplicate breaks/pauses
        for typ, paragraph in tuples_tagged_paragraph_list:
            if typ == "heading":
                # Add heading text to the list after stripping whitespace
                paragraph = paragraph.strip()
                if self.lang == "zh":
                    paragraph = re.sub(r"\s+", TTS_SML_CN['break'], paragraph)
                    paragraph += TTS_SML_CN['break']
                paragraph_text_list.append(paragraph)
            elif typ == "break":
                # Avoid adding multiple consecutive break tokens which could cause unwanted pauses
                if is_tokenizer_tts and prev_typ != 'break':
                    paragraph_text_list.append(TTS_SML['break'])
            elif is_tokenizer_tts and typ == 'pause':
                # Avoid adding multiple consecutive pause tokens which could cause unwanted pauses
                if prev_typ != 'pause':
                    paragraph_text_list.append(TTS_SML['pause'])
            elif typ == "table":
                # Convert HTML tables into a readable string format for TTS
                table = paragraph
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
                        paragraph_text_list.append(line.strip())
            else:
                # Handle regular text content
                text = paragraph.strip()
                if text:
                    paragraph_text_list.append(text)
            prev_typ = typ
        return paragraph_text_list 
