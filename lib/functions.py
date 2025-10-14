# NOTE!!NOTE!!!NOTE!!NOTE!!!NOTE!!NOTE!!!NOTE!!NOTE!!!
# THE WORD "CHAPTER" IN THE CODE DOES NOT MEAN
# IT'S THE REAL CHAPTER OF THE EBOOK SINCE NO STANDARDS
# ARE DEFINING A CHAPTER ON .EPUB FORMAT. THE WORD "BLOCK"
# IS USED TO PRINT IT OUT TO THE TERMINAL, AND "CHAPTER" TO THE CODE
# WHICH IS LESS GENERIC FOR THE DEVELOPERS

import argparse, asyncio, csv, fnmatch, hashlib, io, json, math, os, platform, random, shutil, socket, subprocess, sys, tempfile, threading, time, traceback
import unicodedata, urllib.request, uuid, zipfile, ebooklib, gradio as gr, psutil, pymupdf4llm, regex as re, requests, stanza, torch, uvicorn

from soynlp.tokenizer import LTokenizer
from pythainlp.tokenize import word_tokenize
from sudachipy import dictionary, tokenizer
from PIL import Image
from tqdm import tqdm
from bs4 import BeautifulSoup, NavigableString, Tag
from collections import Counter
from collections.abc import Mapping
from collections.abc import MutableMapping
from datetime import datetime
from ebooklib import epub
from glob import glob
from iso639 import languages
from markdown import markdown
from multiprocessing import Pool, cpu_count
from multiprocessing import Manager, Event
from multiprocessing.managers import DictProxy, ListProxy
from num2words import num2words
from pathlib import Path
from pydub import AudioSegment
from pydub.utils import mediainfo
from queue import Queue, Empty
from types import MappingProxyType
from urllib.parse import urlparse
from starlette.requests import ClientDisconnect

from lib import *
from lib.classes.voice_extractor import VoiceExtractor
from lib.classes.tts_manager import TTSManager
#from lib.classes.redirect_console import RedirectConsole
#from lib.classes.argos_translator import ArgosTranslator

context = None
is_gui_process = False
active_sessions = set()

#import logging
#logging.basicConfig(
#    level=logging.INFO, # DEBUG for more verbosity
#    format="%(asctime)s [%(levelname)s] %(message)s"
#)

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



class SessionContext:
    def __init__(self):
        self.manager = Manager()
        self.sessions = self.manager.dict()
        self.cancellation_events = {}

    def get_session(self, id):
        if id not in self.sessions:
            self.sessions[id] = recursive_proxy({
                "script_mode": NATIVE,
                "id": id,
                "tab_id": None,
                "process_id": None,
                "status": None,
                "event": None,
                "progress": 0,
                "cancellation_requested": False,
                "device": default_device,
                "system": None,
                "client": None,
                "language": default_language_code,
                "language_iso1": None,
                "audiobook": None,
                "audiobooks_dir": None,
                "process_dir": None,
                "ebook": None,
                "ebook_list": None,
                "ebook_mode": "single",
                "chapters_dir": None,
                "chapters_dir_sentences": None,
                "epub_path": None,
                "filename_noext": None,
                "tts_engine": default_tts_engine,
                "fine_tuned": default_fine_tuned,
                "voice": None,
                "voice_dir": None,
                "custom_model": None,
                "custom_model_dir": None,
                "temperature": default_engine_settings[TTS_ENGINES['XTTSv2']]['temperature'],
                "length_penalty": default_engine_settings[TTS_ENGINES['XTTSv2']]['length_penalty'],
                "num_beams": default_engine_settings[TTS_ENGINES['XTTSv2']]['num_beams'],
                "repetition_penalty": default_engine_settings[TTS_ENGINES['XTTSv2']]['repetition_penalty'],
                "top_k": default_engine_settings[TTS_ENGINES['XTTSv2']]['top_k'],
                "top_p": default_engine_settings[TTS_ENGINES['XTTSv2']]['top_p'],
                "speed": default_engine_settings[TTS_ENGINES['XTTSv2']]['speed'],
                "enable_text_splitting": default_engine_settings[TTS_ENGINES['XTTSv2']]['enable_text_splitting'],
                "text_temp": default_engine_settings[TTS_ENGINES['BARK']]['text_temp'],
                "waveform_temp": default_engine_settings[TTS_ENGINES['BARK']]['waveform_temp'],
                "cfg_value": default_engine_settings[TTS_ENGINES['VOXCPM']]['cfg_value'],
                "inference_timesteps": default_engine_settings[TTS_ENGINES['VOXCPM']]['inference_timesteps'],
                "normalize": default_engine_settings[TTS_ENGINES['VOXCPM']]['normalize'],
                "denoise": default_engine_settings[TTS_ENGINES['VOXCPM']]['denoise'],
                "retry_badcase": default_engine_settings[TTS_ENGINES['VOXCPM']]['retry_badcase'],
                "retry_badcase_max_times": default_engine_settings[TTS_ENGINES['VOXCPM']]['retry_badcase_max_times'],
                "retry_badcase_ratio_threshold": default_engine_settings[TTS_ENGINES['VOXCPM']]['retry_badcase_ratio_threshold'],
                "prompt_text": "Default prompt text",
                "final_name": None,
                "output_format": default_output_format,
                "output_split": default_output_split,
                "output_split_hours": default_output_split_hours,
                "metadata": {
                    "title": None, 
                    "creator": None,
                    "contributor": None,
                    "language": None,
                    "identifier": None,
                    "publisher": None,
                    "date": None,
                    "description": None,
                    "subject": None,
                    "rights": None,
                    "format": None,
                    "type": None,
                    "coverage": None,
                    "relation": None,
                    "Source": None,
                    "Modified": None,
                },
                "toc": None,
                "chapters": None,
                "cover": None,
                "duration": 0,
                "playback_time": 0
            }, manager=self.manager)
        return self.sessions[id]

    def find_id_by_hash(self, socket_hash):
        for id, session in self.sessions.items():
            if socket_hash in session:
                return session.get('id')
        return None

def show_alert(state):
    if isinstance(state, dict):
        if state['type'] is not None:
            if state['type'] == 'error':
                gr.Error(state['msg'])
            elif state['type'] == 'warning':
                gr.Warning(state['msg'])
            elif state['type'] == 'info':
                gr.Info(state['msg'])
            elif state['type'] == 'success':
                gr.Success(state['msg'])
def recursive_proxy(data, manager=None):
    if manager is None:
        manager = Manager()
    if isinstance(data, dict):
        proxy_dict = manager.dict()
        for key, value in data.items():
            proxy_dict[key] = recursive_proxy(value, manager)
        return proxy_dict
    elif isinstance(data, list):
        proxy_list = manager.list()
        for item in data:
            proxy_list.append(recursive_proxy(item, manager))
        return proxy_list
    elif isinstance(data, (str, int, float, bool, type(None))):
        return data
    else:
        error = f"Unsupported data type: {type(data)}"
        print(error)
        return

def prepare_dirs(src, session):
    try:
        resume = False
        os.makedirs(os.path.join(models_dir,'tts'), exist_ok=True)
        os.makedirs(session['session_dir'], exist_ok=True)
        os.makedirs(session['process_dir'], exist_ok=True)
        os.makedirs(session['custom_model_dir'], exist_ok=True)
        os.makedirs(session['voice_dir'], exist_ok=True)
        os.makedirs(session['audiobooks_dir'], exist_ok=True)
        session['ebook'] = os.path.join(session['process_dir'], os.path.basename(src))
        if os.path.exists(session['ebook']):
            if compare_files_by_hash(session['ebook'], src):
                resume = True
        if not resume:
            shutil.rmtree(session['chapters_dir'], ignore_errors=True)
        os.makedirs(session['chapters_dir'], exist_ok=True)
        os.makedirs(session['chapters_dir_sentences'], exist_ok=True)
        shutil.copy(src, session['ebook']) 
        return True
    except Exception as e:
        DependencyError(e)
        return False

def check_programs(prog_name, command, options):
    try:
        subprocess.run(
            [command, options],
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            check=True,
            text=True,
            encoding='utf-8'
        )
        return True, None
    except FileNotFoundError:
        e = f'''********** Error: {prog_name} is not installed! if your OS calibre package version 
        is not compatible you still can run ebook2audiobook.sh (linux/mac) or ebook2audiobook.cmd (windows) **********'''
        DependencyError(e)
        return False, None
    except subprocess.CalledProcessError:
        e = f'Error: There was an issue running {prog_name}.'
        DependencyError(e)
        return False, None

def analyze_uploaded_file(zip_path, required_files):
    try:
        if not os.path.exists(zip_path):
            error = f"The file does not exist: {os.path.basename(zip_path)}"
            print(error)
            return False
        files_in_zip = {}
        empty_files = set()
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for file_info in zf.infolist():
                file_name = file_info.filename
                if file_info.is_dir():
                    continue
                base_name = os.path.basename(file_name)
                files_in_zip[base_name.lower()] = file_info.file_size
                if file_info.file_size == 0:
                    empty_files.add(base_name.lower())
        required_files = [file.lower() for file in required_files]
        missing_files = [f for f in required_files if f not in files_in_zip]
        required_empty_files = [f for f in required_files if f in empty_files]
        if missing_files:
            print(f"Missing required files: {missing_files}")
        if required_empty_files:
            print(f"Required files with 0 KB: {required_empty_files}")
        return not missing_files and not required_empty_files
    except zipfile.BadZipFile:
        error = "The file is not a valid ZIP archive."
        raise ValueError(error)
    except Exception as e:
        error = f"An error occurred: {e}"
        raise RuntimeError(error)

def extract_custom_model(file_src, session, required_files=None):
    try:
        model_path = None
        if required_files is None:
            required_files = models[session['tts_engine']][default_fine_tuned]['files']
        model_name = re.sub('.zip', '', os.path.basename(file_src), flags=re.IGNORECASE)
        model_name = get_sanitized(model_name)
        with zipfile.ZipFile(file_src, 'r') as zip_ref:
            files = zip_ref.namelist()
            files_length = len(files)
            tts_dir = session['tts_engine']
            model_path = os.path.join(session['custom_model_dir'], tts_dir, model_name)
            if os.path.exists(model_path):
                print(f'{model_path} already exists, bypassing files extraction')
                return model_path
            os.makedirs(model_path, exist_ok=True)
            required_files_lc = set(x.lower() for x in required_files)
            with tqdm(total=files_length, unit='files') as t:
                for f in files:
                    base_f = os.path.basename(f).lower()
                    if base_f in required_files_lc:
                        out_path = os.path.join(model_path, base_f)
                        with zip_ref.open(f) as src, open(out_path, 'wb') as dst:
                            shutil.copyfileobj(src, dst)
                    t.update(1)
        if is_gui_process:
            os.remove(file_src)
        if model_path is not None:
            msg = f'Extracted files to {model_path}'
            print(msg)
            return model_path
        else:
            error = f'An error occured when unzip {file_src}'
            return None
    except asyncio.exceptions.CancelledError as e:
        DependencyError(e)
        if is_gui_process:
            os.remove(file_src)
        return None       
    except Exception as e:
        DependencyError(e)
        if is_gui_process:
            os.remove(file_src)
        return None
        
def hash_proxy_dict(proxy_dict):
    return hashlib.md5(str(proxy_dict).encode('utf-8')).hexdigest()

def calculate_hash(filepath, hash_algorithm='sha256'):
    hash_func = hashlib.new(hash_algorithm)
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):  # Read in chunks to handle large files
            hash_func.update(chunk)
    return hash_func.hexdigest()

def compare_files_by_hash(file1, file2, hash_algorithm='sha256'):
    return calculate_hash(file1, hash_algorithm) == calculate_hash(file2, hash_algorithm)

def compare_dict_keys(d1, d2):
    if not isinstance(d1, Mapping) or not isinstance(d2, Mapping):
        return d1 == d2
    d1_keys = set(d1.keys())
    d2_keys = set(d2.keys())
    missing_in_d2 = d1_keys - d2_keys
    missing_in_d1 = d2_keys - d1_keys
    if missing_in_d2 or missing_in_d1:
        return {
            "missing_in_d2": missing_in_d2,
            "missing_in_d1": missing_in_d1,
        }
    for key in d1_keys.intersection(d2_keys):
        nested_result = compare_keys(d1[key], d2[key])
        if nested_result:
            return {key: nested_result}
    return None

def proxy2dict(proxy_obj):
    def recursive_copy(source, visited):
        # Handle circular references by tracking visited objects
        if id(source) in visited:
            return None  # Stop processing circular references
        visited.add(id(source))  # Mark as visited
        if isinstance(source, dict):
            result = {}
            for key, value in source.items():
                result[key] = recursive_copy(value, visited)
            return result
        elif isinstance(source, list):
            return [recursive_copy(item, visited) for item in source]
        elif isinstance(source, set):
            return list(source)
        elif isinstance(source, (int, float, str, bool, type(None))):
            return source
        elif isinstance(source, DictProxy):
            # Explicitly handle DictProxy objects
            return recursive_copy(dict(source), visited)  # Convert DictProxy to dict
        else:
            return str(source)  # Convert non-serializable types to strings
    return recursive_copy(proxy_obj, set())

def convert2epub(id):
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

def get_ebook_title(epubBook, all_docs):
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

def get_cover(epubBook, session):
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

def get_chapters(epubBook, session):
    try:
        msg = r'''
*******************************************************************************
NOTE:
The warning "Character xx not found in the vocabulary."
MEANS THE MODEL CANNOT INTERPRET THE CHARACTER AND WILL MAYBE GENERATE
(AS WELL AS WRONG PUNCTUATION POSITION) AN HALLUCINATION TO IMPROVE THIS MODEL,
IT NEEDS TO ADD THIS CHARACTER INTO A NEW TRAINING MODEL.
YOU CAN IMPROVE IT OR ASK TO A TRAINING MODEL EXPERT.
*******************************************************************************
        '''
        print(msg)
        if session['cancellation_requested']:
            print('Cancel requested')
            return False
        # Step 1: Extract TOC (Table of Contents)
        try:
            toc = epubBook.toc  # Extract TOC
            toc_list = [
                    nt for item in toc if hasattr(item, 'title')
                    if (nt := normalize_text(
                        str(item.title),
                        session['language'],
                        session['language_iso1'],
                        session['tts_engine']
                )) is not None
            ]
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
        if not all_docs:
            return [], []
        title = get_ebook_title(epubBook, all_docs)
        chapters = []
        stanza_nlp = False
        if session['language'] in year_to_decades_languages:
            stanza.download(session['language_iso1'])
            stanza_nlp = stanza.Pipeline(session['language_iso1'], processors='tokenize,ner')
        is_num2words_compat = get_num2words_compat(session['language_iso1'])
        msg = 'Analyzing numbers, maths signs, dates and time to convert in words...'
        print(msg)
        for doc in all_docs:
            sentences_list = filter_chapter(doc, session['language'], session['language_iso1'], session['tts_engine'], stanza_nlp, is_num2words_compat)
            if sentences_list is None:
                break
            elif len(sentences_list) > 0:
                chapters.append(sentences_list)
        if len(chapters) == 0:
            error = 'No chapters found!'
            return None, None
        return toc, chapters
    except Exception as e:
        error = f'Error extracting main content pages: {e}'
        DependencyError(error)
        return None, None

def filter_chapter(doc, lang, lang_iso1, tts_engine, stanza_nlp, is_num2words_compat):

    def tuple_row(node, last_text_char=None):
        try:
            for child in node.children:
                if isinstance(child, NavigableString):
                    text = child.strip()
                    if text:
                        yield ("text", text)
                        last_text_char = text[-1] if text else last_text_char

                elif isinstance(child, Tag):
                    name = child.name.lower()
                    if name in heading_tags:
                        title = child.get_text(strip=True)
                        if title:
                            yield ("heading", title)
                            last_text_char = title[-1] if title else last_text_char

                    elif name == "table":
                        yield ("table", child)

                    else:
                        return_data = False
                        if name in proc_tags:
                            for inner in tuple_row(child, last_text_char):
                                return_data = True
                                yield inner
                                # Track last char if this is text or heading
                                if inner[0] in ("text", "heading") and inner[1]:
                                    last_text_char = inner[1][-1]

                            if return_data:
                                if name in break_tags:
                                    # Only yield break if last char is NOT alnum or space
                                    if not (last_text_char and (last_text_char.isalnum() or last_text_char.isspace())):
                                        yield ("break", TTS_SML['break'])
                                elif name in heading_tags or name in pause_tags:
                                    yield ("pause", TTS_SML['pause'])

                        else:
                            yield from tuple_row(child, last_text_char)

        except Exception as e:
            error = f'filter_chapter() tuple_row() error: {e}'
            DependencyError(error)
            return None

    try:
        heading_tags = [f'h{i}' for i in range(1, 5)]
        break_tags = ['br', 'p']
        pause_tags = ['div', 'span']
        proc_tags = heading_tags + break_tags + pause_tags
        raw_html = doc.get_body_content().decode("utf-8")
        soup = BeautifulSoup(raw_html, 'html.parser')
        body = soup.body
        if not body or not body.get_text(strip=True):
            return []
        # Skip known non-chapter types
        epub_type = body.get("epub:type", "").lower()
        if not epub_type:
            section_tag = soup.find("section")
            if section_tag:
                epub_type = section_tag.get("epub:type", "").lower()
        excluded = {
            "frontmatter", "backmatter", "toc", "titlepage", "colophon",
            "acknowledgments", "dedication", "glossary", "index",
            "appendix", "bibliography", "copyright-page", "landmark"
        }
        if any(part in epub_type for part in excluded):
            return []
        # remove scripts/styles
        for tag in soup(["script", "style"]):
            tag.decompose()
        tuples_list = list(tuple_row(body))
        if not tuples_list:
            error = 'No tuples_list from body created!'
            print(error)
            return None
        text_list = []
        handled_tables = set()
        prev_typ = None
        for typ, payload in tuples_list:
            if typ == "heading":
                text_list.append(payload.strip())
            elif typ == "break":
                if prev_typ != 'break':
                    text_list.append(TTS_SML['break'])
            elif typ == 'pause':
                if prev_typ != 'pause':
                    text_list.append(TTS_SML['pause'])
            elif typ == "table":
                table = payload
                if table in handled_tables:
                    prev_typ = typ
                    continue
                handled_tables.add(table)
                rows = table.find_all("tr")
                if not rows:
                    prev_typ = typ
                    continue
                headers = [c.get_text(strip=True) for c in rows[0].find_all(["td", "th"])]
                for row in rows[1:]:
                    cells = [c.get_text(strip=True).replace('\xa0', ' ') for c in row.find_all("td")]
                    if not cells:
                        continue
                    if len(cells) == len(headers) and headers:
                        line = " — ".join(f"{h}: {c}" for h, c in zip(headers, cells))
                    else:
                        line = " — ".join(cells)
                    if line:
                        text_list.append(line.strip())
            else:
                text = payload.strip()
                if text:
                    text_list.append(text)
            prev_typ = typ
        max_chars = language_mapping[lang]['max_chars'] - 4
        clean_list = []
        i = 0
        while i < len(text_list):
            current = text_list[i]
            if current == "‡break‡":
                if clean_list:
                    prev = clean_list[-1]
                    if prev in ("‡break‡", "‡pause‡"):
                        i += 1
                        continue
                    if prev and (prev[-1].isalnum() or prev[-1] == ' '):
                        if i + 1 < len(text_list):
                            next_sentence = text_list[i + 1]
                            merged_length = len(prev.rstrip()) + 1 + len(next_sentence.lstrip())
                            if merged_length <= max_chars:
                                # Merge with space handling
                                if not prev.endswith(" ") and not next_sentence.startswith(" "):
                                    clean_list[-1] = prev + " " + next_sentence
                                else:
                                    clean_list[-1] = prev + next_sentence
                                i += 2
                                continue
                            else:
                                clean_list.append(current)
                                i += 1
                                continue
            clean_list.append(current)
            i += 1
        text = ' '.join(clean_list)
        if not re.search(r"[^\W_]", text):
            error = 'No valid text found!'
            print(error)
            return None
        if stanza_nlp:
            # Check if there are positive integers so possible date to convert
            re_ordinal = re.compile(
                r'(?<!\w)(0?[1-9]|[12][0-9]|3[01])(?:\s|\u00A0)*(?:st|nd|rd|th)(?!\w)',
                re.IGNORECASE
            )
            re_num = re.compile(r'(?<!\w)[-+]?\d+(?:\.\d+)?(?!\w)')
            text = unicodedata.normalize('NFKC', text).replace('\u00A0', ' ')
            if re_num.search(text) and re_ordinal.search(text):
                date_spans = get_date_entities(text, stanza_nlp)
                if date_spans:
                    result = []
                    last_pos = 0
                    for start, end, date_text in date_spans:
                        result.append(text[last_pos:start])
                        # 1) convert 4-digit years (your original behavior)
                        processed = re.sub(
                            r"\b\d{4}\b",
                            lambda m: year2words(m.group(), lang, lang_iso1, is_num2words_compat),
                            date_text
                        )
                        # 2) convert ordinal days like "16th"/"16 th" -> "sixteenth"
                        if is_num2words_compat:
                            processed = re_ordinal.sub(
                                lambda m: num2words(int(m.group(1)), to="ordinal", lang=(lang_iso1 or "en")),
                                processed
                            )
                        else:
                            processed = re_ordinal.sub(
                                lambda m: math2words(m.group(), lang, lang_iso1, tts_engine, is_num2words_compat),
                                processed
                            )
                        # 3) convert other numbers (skip 4-digit years)
                        def _num_repl(m):
                            s = m.group(0)
                            # leave years alone (already handled above)
                            if re.fullmatch(r"\d{4}", s):
                                return s
                            n = float(s) if "." in s else int(s)
                            if is_num2words_compat:
                                return num2words(n, lang=(lang_iso1 or "en"))
                            else:
                                return math2words(m, lang, lang_iso1, tts_engine, is_num2words_compat)

                        processed = re_num.sub(_num_repl, processed)
                        result.append(processed)
                        last_pos = end
                    result.append(text[last_pos:])
                    text = ''.join(result)
                else:
                    if is_num2words_compat:
                        text = re_ordinal.sub(
                            lambda m: num2words(int(m.group(1)), to="ordinal", lang=(lang_iso1 or "en")),
                            text
                        )
                    else:
                        text = re_ordinal.sub(
                            lambda m: math2words(int(m.group(1)), lang, lang_iso1, tts_engine, is_num2words_compat),
                            text
                        )
                    text = re.sub(
                        r"\b\d{4}\b",
                        lambda m: year2words(m.group(), lang, lang_iso1, is_num2words_compat),
                        text
                    )
        text = roman2number(text)
        text = clock2words(text, lang, lang_iso1, tts_engine, is_num2words_compat)
        text = math2words(text, lang, lang_iso1, tts_engine, is_num2words_compat)
        # build a translation table mapping each bad char to a space
        specialchars_remove_table = str.maketrans({ch: ' ' for ch in specialchars_remove})
        text = text.translate(specialchars_remove_table)
        text = normalize_text(text, lang, lang_iso1, tts_engine)
        # Ensure space before and after punctuation_list
        #pattern_space = re.escape(''.join(punctuation_list))
        #punctuation_pattern_space = r'(?<!\s)([{}])'.format(pattern_space)
        #text = re.sub(punctuation_pattern_space, r' \1', text)
        sentences = get_sentences(text, lang, tts_engine)
        if len(sentences) == 0:
            error = 'No sentences found!'
            print(error)
            return None
        return get_sentences(text, lang, tts_engine)
    except Exception as e:
        error = f'filter_chapter() error: {e}'
        DependencyError(error)
        return None

def get_sentences(text, lang, tts_engine):

    def split_inclusive(text, pattern):
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

    def segment_ideogramms(text):
        sml_pattern = "|".join(re.escape(token) for token in sml_tokens)
        segments = re.split(f"({sml_pattern})", text)
        result = []
        try:
            for segment in segments:
                if not segment:
                    continue
                # If the segment is a SML token, keep as its own
                if re.fullmatch(sml_pattern, segment):
                    result.append(segment)
                else:
                    if lang == 'zho':
                        import jieba
                        result.extend([t for t in jieba.cut(segment) if t.strip()])
                    elif lang == 'jpn':
                        sudachi = dictionary.Dictionary().create()
                        mode = tokenizer.Tokenizer.SplitMode.C
                        result.extend([m.surface() for m in sudachi.tokenize(segment, mode) if m.surface().strip()])
                    elif lang == 'kor':
                        ltokenizer = LTokenizer()
                        result.extend([t for t in ltokenizer.tokenize(segment) if t.strip()])
                    elif lang in ['tha', 'lao', 'mya', 'khm']:
                        result.extend([t for t in word_tokenize(segment, engine='newmm') if t.strip()])
                    else:
                        result.append(segment.strip())
            return result
        except Exception as e:
            DependencyError(e)
            return [text]   

    def join_ideogramms(idg_list):
        try:
            buffer = ''
            for token in idg_list:
             # 1) On sml token: flush & emit buffer, then emit the token
                if token.strip() in sml_tokens:
                    if buffer:
                        yield buffer
                        buffer = ''
                    yield token
                    continue
                # 2) If adding this token would overflow, flush current buffer first
                if buffer and len(buffer) + len(token) > max_chars:
                    yield buffer
                    buffer = ''
                # 3) Append the token (word, punctuation, whatever) unless it's a sml token (already checked)
                buffer += token
            # 4) Flush any trailing text
            if buffer:
                yield buffer
        except Exception as e:
            DependencyError(e)
            if buffer:
                yield buffer

    try:
        max_chars = language_mapping[lang]['max_chars'] - 4
        min_tokens = 5
        # List or tuple of tokens that must never be appended to buffer
        sml_tokens = tuple(TTS_SML.values())
        sml_list = re.split(rf"({'|'.join(map(re.escape, sml_tokens))})", text)
        sml_list = [s for s in sml_list if s.strip() or s in sml_tokens]
        pattern_split = '|'.join(map(re.escape, punctuation_split_hard_set))
        pattern = re.compile(rf"(.*?(?:{pattern_split}){''.join(punctuation_list_set)})(?=\s|$)", re.DOTALL)
        hard_list = []
        for s in sml_list:
            if s in [TTS_SML['break'], TTS_SML['pause']] or len(s) <= max_chars:
                hard_list.append(s)
            else:
                parts = split_inclusive(s, pattern)
                if parts:
                    for text_part in parts:
                        text_part = text_part.strip()
                        if text_part:
                            hard_list.append(text_part)
                else:
                    s = s.strip()
                    if s:
                        hard_list.append(s)
        # Check if some hard_list entries exceed max_chars, so split on soft punctuation
        pattern_split = '|'.join(map(re.escape, punctuation_split_soft_set))
        pattern = re.compile(rf"(.*?(?:{pattern_split}))(?=\s|$)", re.DOTALL)
        soft_list = []
        for s in hard_list:
            if s in [TTS_SML['break'], TTS_SML['pause']] or len(s) <= max_chars:
                soft_list.append(s)
            elif len(s) > max_chars:
                parts = [p for p in split_inclusive(s, pattern) if p]
                if parts:
                    buffer = ''
                    for idx, part in enumerate(parts):
                        # Predict length if we glue this part
                        predicted_length = len(buffer) + (1 if buffer else 0) + len(part)
                        # Peek ahead to see if gluing will exceed max_chars
                        if predicted_length <= max_chars:
                            buffer = (buffer + ' ' + part).strip() if buffer else part
                        else:
                            # If we overshoot, check if buffer ends with punctuation
                            if buffer and not any(buffer.rstrip().endswith(p) for p in punctuation_split_soft_set):
                                # Try to backtrack to last punctuation inside buffer
                                last_punct_idx = max((buffer.rfind(p) for p in punctuation_split_soft_set if p in buffer), default=-1)
                                if last_punct_idx != -1:
                                    soft_list.append(buffer[:last_punct_idx+1].strip())
                                    leftover = buffer[last_punct_idx+1:].strip()
                                    buffer = leftover + ' ' + part if leftover else part
                                else:
                                    # No punctuation, just split as-is
                                    soft_list.append(buffer.strip())
                                    buffer = part
                            else:
                                soft_list.append(buffer.strip())
                                buffer = part
                    if buffer:
                        cleaned = re.sub(r'[^\p{L}\p{N} ]+', '', buffer)
                        if any(ch.isalnum() for ch in cleaned):
                            soft_list.append(buffer.strip())
                else:
                    cleaned = re.sub(r'[^\p{L}\p{N} ]+', '', s)
                    if any(ch.isalnum() for ch in cleaned):
                        soft_list.append(s.strip())
            else:
                cleaned = re.sub(r'[^\p{L}\p{N} ]+', '', s)
                if any(ch.isalnum() for ch in cleaned):
                    soft_list.append(s.strip())

        if lang in ['zho', 'jpn', 'kor', 'tha', 'lao', 'mya', 'khm']:
            result = []
            for s in soft_list:
                if s in [TTS_SML['break'], TTS_SML['pause']]:
                    result.append(s)
                else:
                    tokens = segment_ideogramms(s)
                    if isinstance(tokens, list):
                        result.extend([t for t in tokens if t.strip()])
                    else:
                        tokens = tokens.strip()
                        if tokens:
                            result.append(tokens)
            return list(join_ideogramms(result))
        else:
            sentences = []
            for s in soft_list:
                if s in [TTS_SML['break'], TTS_SML['pause']] or len(s) <= max_chars:
                    sentences.append(s)
                else:
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
        
def get_ram():
    vm = psutil.virtual_memory()
    return vm.total // (1024 ** 3)

def get_vram():
    os_name = platform.system()
    # NVIDIA (Cross-Platform: Windows, Linux, macOS)
    try:
        from pynvml import nvmlInit, nvmlDeviceGetHandleByIndex, nvmlDeviceGetMemoryInfo
        nvmlInit()
        handle = nvmlDeviceGetHandleByIndex(0)  # First GPU
        info = nvmlDeviceGetMemoryInfo(handle)
        vram = info.total
        return int(vram // (1024 ** 3))  # Convert to GB
    except ImportError:
        pass
    except Exception as e:
        pass
    # AMD (Windows)
    if os_name == "Windows":
        try:
            cmd = 'wmic path Win32_VideoController get AdapterRAM'
            output = subprocess.run(cmd, capture_output=True, text=True, shell=True)
            lines = output.stdout.splitlines()
            vram_values = [int(line.strip()) for line in lines if line.strip().isdigit()]
            if vram_values:
                return int(vram_values[0] // (1024 ** 3))
        except Exception as e:
            pass
    # AMD (Linux)
    if os_name == "Linux":
        try:
            cmd = "lspci -v | grep -i 'VGA' -A 12 | grep -i 'preallocated' | awk '{print $2}'"
            output = subprocess.run(cmd, capture_output=True, text=True, shell=True)
            if output.stdout.strip().isdigit():
                return int(output.stdout.strip()) // 1024
        except Exception as e:
            pass
    # Intel (Linux Only)
    intel_vram_paths = [
        "/sys/kernel/debug/dri/0/i915_vram_total",  # Intel dedicated GPUs
        "/sys/class/drm/card0/device/resource0"  # Some integrated GPUs
    ]
    for path in intel_vram_paths:
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    vram = int(f.read().strip()) // (1024 ** 3)
                    return vram
            except Exception as e:
                pass
    # macOS (OpenGL Alternative)
    if os_name == "Darwin":
        try:
            from OpenGL.GL import glGetIntegerv
            from OpenGL.GLX import GLX_RENDERER_VIDEO_MEMORY_MB_MESA
            vram = int(glGetIntegerv(GLX_RENDERER_VIDEO_MEMORY_MB_MESA) // 1024)
            return vram
        except ImportError:
            pass
        except Exception as e:
            pass
    msg = 'Could not detect GPU VRAM Capacity!'
    return 0

def get_sanitized(str, replacement="_"):
    str = str.replace('&', 'And')
    forbidden_chars = r'[<>:"/\\|?*\x00-\x1F ()]'
    sanitized = re.sub(r'\s+', replacement, str)
    sanitized = re.sub(forbidden_chars, replacement, sanitized)
    sanitized = sanitized.strip("_")
    return sanitized
    
def get_date_entities(text, stanza_nlp):
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

def get_num2words_compat(lang_iso1):
    try:
        test = num2words(1, lang=lang_iso1.replace('zh', 'zh_CN'))
        return True
    except NotImplementedError:
        return False
    except Exception as e:
        return False

def set_formatted_number(text: str, lang, lang_iso1: str, is_num2words_compat: bool, max_single_value: int = 999_999_999_999_999_999):
    # match up to 18 digits, optional “,…” groups (allowing spaces or NBSP after comma), optional decimal of up to 12 digits
    # handle optional range with dash/en dash/em dash between numbers, and allow trailing punctuation
    number_re = re.compile(
        r'(?<!\w)'
        r'(\d{1,18}(?:,\s*\d{1,18})*(?:\.\d{1,12})?)'      # first number
        r'(?:\s*([-–—])\s*'                                # dash type
        r'(\d{1,18}(?:,\s*\d{1,18})*(?:\.\d{1,12})?))?'    # optional second number
        r'([^\w\s]*)',                                     # optional trailing punctuation
        re.UNICODE
    )

    def normalize_commas(num_str: str) -> str:
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

    def clean_single_num(num_str):
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
        tok = normalize_commas(tok)

        if is_num2words_compat:
            new_lang_iso1 = lang_iso1.replace('zh', 'zh_CN')
            return num2words(num, lang=new_lang_iso1)
        else:
            phoneme_map = language_math_phonemes.get(
                lang,
                language_math_phonemes.get(default_language_code, language_math_phonemes['eng'])
            )
            return ' '.join(phoneme_map.get(ch, ch) for ch in str(num))

    def clean_match(match):
        first_num = clean_single_num(match.group(1))
        dash_char = match.group(2) or ''
        second_num = clean_single_num(match.group(3)) if match.group(3) else ''
        trailing = match.group(4) or ''
        if second_num:
            return f"{first_num}{dash_char}{second_num}{trailing}"
        else:
            return f"{first_num}{trailing}"

    return number_re.sub(clean_match, text)

def year2words(year_str, lang, lang_iso1, is_num2words_compat):
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

def clock2words(text, lang, lang_iso1, tts_engine, is_num2words_compat):
    time_rx = re.compile(r'(\d{1,2})[:.](\d{1,2})(?:[:.](\d{1,2}))?')
    lang_lc = (lang or "").lower()
    lc = language_clock.get(lang_lc) if 'language_clock' in globals() else None
    _n2w_cache = {}

    def n2w(n: int) -> str:
        key = (n, lang_lc, is_num2words_compat)
        if key in _n2w_cache:
            return _n2w_cache[key]
        if is_num2words_compat:
            word = num2words(n, lang=lang_lc)
        else:
            word = math2words(n, lang, lang_iso1, tts_engine, is_num2words_compat)
        _n2w_cache[key] = word
        return word

    def repl_num(m: re.Match) -> str:
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
            parts = [n2w(h)]
            if mnt != 0:
                parts.append(n2w(mnt))
            if sec is not None and sec > 0:
                parts.append(n2w(sec))
            return " ".join(parts)

        next_hour = (h + 1) % 24
        special_hours = lc.get("special_hours", {})
        # Build main phrase
        if mnt == 0 and (sec is None or sec == 0):
            if h in special_hours:
                phrase = special_hours[h]
            else:
                phrase = lc["oclock"].format(hour=n2w(h))
        elif mnt == 15:
            phrase = lc["quarter_past"].format(hour=n2w(h))
        elif mnt == 30:
            # German "halb drei" (= 2:30) uses next hour
            if lang_lc == "deu":
                phrase = lc["half_past"].format(next_hour=n2w(next_hour))
            else:
                phrase = lc["half_past"].format(hour=n2w(h))
        elif mnt == 45:
            phrase = lc["quarter_to"].format(next_hour=n2w(next_hour))
        elif mnt < 30:
            phrase = lc["past"].format(hour=n2w(h), minute=n2w(mnt)) if mnt != 0 else lc["oclock"].format(hour=n2w(h))
        else:
            minute_to_hour = 60 - mnt
            phrase = lc["to"].format(next_hour=n2w(next_hour), minute=n2w(minute_to_hour))
        # Append seconds if present
        if sec is not None and sec > 0:
            second_phrase = lc["second"].format(second=n2w(sec))
            phrase = lc["full"].format(phrase=phrase, second_phrase=second_phrase)
        return phrase

    return time_rx.sub(repl_num, text)

def math2words(text, lang, lang_iso1, tts_engine, is_num2words_compat):

    def repl_ambiguous(match):
        # handles "num SYMBOL num" and "SYMBOL num"
        if match.group(2) and match.group(2) in ambiguous_replacements:
            return f"{match.group(1)} {ambiguous_replacements[match.group(2)]} {match.group(3)}"
        if match.group(3) and match.group(3) in ambiguous_replacements:
            return f"{ambiguous_replacements[match.group(3)]} {match.group(4)}"
        return match.group(0)

    def _ordinal_to_words(m):
        n = int(m.group(1))
        if is_num2words_compat:
            try:
                from num2words import num2words
                return num2words(n, to="ordinal", lang=(lang_iso1 or "en"))
            except Exception:
                pass
        # If num2words isn't available/compatible, keep original token as-is.
        return m.group(0)

    # Matches any digits + optional space/NBSP + st/nd/rd/th, not glued into words.
    re_ordinal = re.compile(r'(?<!\w)(\d+)(?:\s|\u00A0)*(?:st|nd|rd|th)(?!\w)')
    text = re.sub(r'(\d)\)', r'\1 : ', text)
    text = re_ordinal.sub(_ordinal_to_words, text)
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
        text = re.sub(ambiguous_pattern, repl_ambiguous, text)
    text = set_formatted_number(text, lang, lang_iso1, is_num2words_compat)
    return text

def roman2number(text):

    def is_valid_roman(s):
        return bool(valid_roman.fullmatch(s))

    def to_int(s):
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

    def repl_heading(m):
        roman = m.group(1)
        if not is_valid_roman(roman):
            return m.group(0)
        val = to_int(roman)
        return f"{val}{m.group(2)}{m.group(3)}"

    def repl_standalone(m):
        roman = m.group(1)
        if not is_valid_roman(roman):
            return m.group(0)
        val = to_int(roman)
        return f"{val}{m.group(2)}"

    def repl_word(m):
        roman = m.group(1)
        if not is_valid_roman(roman):
            return m.group(0)
        val = to_int(roman)
        return str(val)

    # Well-formed Romans up to 3999
    valid_roman = re.compile(
        r'^(?=.)M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$',
        re.IGNORECASE
    )

    # Your heading/standalone rules stay
    text = re.sub(r'^(?:\s*)([IVXLCDM]+)([.-])(\s+)', repl_heading, text, flags=re.MULTILINE)
    text = re.sub(r'^(?:\s*)([IVXLCDM]+)([.-])(?:\s*)$', repl_standalone, text, flags=re.MULTILINE)

    # NEW: only convert whitespace-delimited tokens of length >= 2
    # This avoids: 19C, 19°C, °C, AC/DC, CD-ROM, single-letter "I"
    text = re.sub(r'(?<!\S)([IVXLCDM]{2,})(?!\S)', repl_word, text)

    return text

def filter_sml(text):
    for key, value in TTS_SML.items():
        pattern = re.escape(key) if key == '###' else r'\[' + re.escape(key) + r'\]'
        text = re.sub(pattern, f" {value} ", text)
    return text

def normalize_text(text, lang, lang_iso1, tts_engine):
    # Remove emojis
    emoji_pattern = re.compile(f"[{''.join(emojis_list)}]+", flags=re.UNICODE)
    emoji_pattern.sub('', text)
    if lang in abbreviations_mapping:
        def repl_abbreviations(match: re.Match) -> str:
            token = match.group(1)
            for k, expansion in mapping.items():
                if token.lower() == k.lower():
                    return expansion
            return token  # fallback
        mapping = abbreviations_mapping[lang]
        # Sort keys by descending length so longer ones match first
        keys = sorted(mapping.keys(), key=len, reverse=True)
        # Build a regex that only matches whole “words” (tokens) exactly
        pattern = re.compile(
            r'(?<!\w)(' + '|'.join(re.escape(k) for k in keys) + r')(?!\w)',
            flags=re.IGNORECASE
        )
        text = pattern.sub(repl_abbreviations, text)
    # This regex matches sequences like a., c.i.a., f.d.a., m.c., etc...
    pattern = re.compile(r'\b(?:[a-zA-Z]\.){1,}[a-zA-Z]?\b\.?')
    # uppercase acronyms
    text = re.sub(r'\b(?:[a-zA-Z]\.){1,}[a-zA-Z]?\b\.?', lambda m: m.group().replace('.', '').upper(), text)
    # Prepare SML tags
    text = filter_sml(text)
    # Replace multiple newlines ("\n\n", "\r\r", "\n\r", etc.) with a ‡pause‡ 1.4sec
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

def convert_chapters2audio(id):
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

def assemble_chunks(txt_file, out_file):
    try:
        ffmpeg_cmd = [
            shutil.which('ffmpeg'), '-hide_banner', '-nostats', '-y',
            '-safe', '0', '-f', 'concat', '-i', txt_file,
            '-c:a', default_audio_proc_format, '-map_metadata', '-1', '-threads', '1', out_file
        ]
        process = subprocess.Popen(
            ffmpeg_cmd,
            env={},
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding='utf-8',
            errors='ignore'
        )
        for line in process.stdout:
            print(line, end='')  # Print each line of stdout
        process.wait()
        if process.returncode == 0:
            return True
        else:
            error = process.returncode
            print(error, ffmpeg_cmd)
            return False
    except subprocess.CalledProcessError as e:
        DependencyError(e)
        return False
    except Exception as e:
        error = f"assemble_chanks() Error: Failed to process {txt_file} → {out_file}: {e}"
        print(error)
        return False

def combine_audio_sentences(chapter_audio_file, start, end, session):
    try:
        chapter_audio_file = os.path.join(session['chapters_dir'], chapter_audio_file)
        chapters_dir_sentences = session['chapters_dir_sentences']
        batch_size = 1024
        sentence_files = [
            f for f in os.listdir(chapters_dir_sentences)
            if f.endswith(f'.{default_audio_proc_format}')
        ]
        sentences_ordered = sorted(
            sentence_files, key=lambda x: int(os.path.splitext(x)[0])
        )
        selected_files = [
            os.path.join(chapters_dir_sentences, f)
            for f in sentences_ordered
            if start <= int(os.path.splitext(f)[0]) <= end
        ]
        if not selected_files:
            print('No audio files found in the specified range.')
            return False
        with tempfile.TemporaryDirectory() as tmpdir:
            chunk_list = []
            for i in range(0, len(selected_files), batch_size):
                batch = selected_files[i:i + batch_size]
                txt = os.path.join(tmpdir, f'chunk_{i:04d}.txt')
                out = os.path.join(tmpdir, f'chunk_{i:04d}.{default_audio_proc_format}')
                with open(txt, 'w') as f:
                    for file in batch:
                        f.write(f"file '{file.replace(os.sep, '/')}'\n")
                chunk_list.append((txt, out))
            try:
                with Pool(cpu_count()) as pool:
                    results = pool.starmap(assemble_chunks, chunk_list)
            except Exception as e:
                error = f"combine_audio_sentences() multiprocessing error: {e}"
                print(error)
                return False
            if not all(results):
                error = "combine_audio_sentences() One or more chunks failed."
                print(error)
                return False
            # Final merge
            final_list = os.path.join(tmpdir, 'sentences_final.txt')
            with open(final_list, 'w') as f:
                for _, chunk_path in chunk_list:
                    f.write(f"file '{chunk_path.replace(os.sep, '/')}'\n")
            if assemble_chunks(final_list, chapter_audio_file):
                msg = f'********* Combined chapter audio file saved in {chapter_audio_file}'
                print(msg)
                return True
            else:
                error = "combine_audio_sentences() Final merge failed."
                print(error)
                return False
    except Exception as e:
        DependencyError(e)
        return False

def combine_audio_chapters(id):

    def get_audio_duration(filepath):
        try:
            ffprobe_cmd = [
                shutil.which('ffprobe'),
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'json',
                filepath
            ]
            result = subprocess.run(ffprobe_cmd, capture_output=True, text=True)
            try:
                return float(json.loads(result.stdout)['format']['duration'])
            except Exception:
                return 0
        except subprocess.CalledProcessError as e:
            DependencyError(e)
            return 0
        except Exception as e:
            error = f"get_audio_duration() Error: Failed to process {txt_file} → {out_file}: {e}"
            print(error)
            return 0

    def generate_ffmpeg_metadata(part_chapters, session, output_metadata_path, default_audio_proc_format):
        try:
            out_fmt = session['output_format']
            is_mp4_like = out_fmt in ['mp4', 'm4a', 'm4b', 'mov']
            is_vorbis = out_fmt in ['ogg', 'webm']
            is_mp3 = out_fmt == 'mp3'
            def tag(key):
                return key.upper() if is_vorbis else key
            ffmpeg_metadata = ';FFMETADATA1\n'
            if session['metadata'].get('title'):
                ffmpeg_metadata += f"{tag('title')}={session['metadata']['title']}\n"
            if session['metadata'].get('creator'):
                ffmpeg_metadata += f"{tag('artist')}={session['metadata']['creator']}\n"
            if session['metadata'].get('language'):
                ffmpeg_metadata += f"{tag('language')}={session['metadata']['language']}\n"
            if session['metadata'].get('description'):
                ffmpeg_metadata += f"{tag('description')}={session['metadata']['description']}\n"
            if session['metadata'].get('publisher') and (is_mp4_like or is_mp3):
                ffmpeg_metadata += f"{tag('publisher')}={session['metadata']['publisher']}\n"
            if session['metadata'].get('published'):
                try:
                    if '.' in session['metadata']['published']:
                        year = datetime.strptime(session['metadata']['published'], '%Y-%m-%dT%H:%M:%S.%f%z').year
                    else:
                        year = datetime.strptime(session['metadata']['published'], '%Y-%m-%dT%H:%M:%S%z').year
                except Exception:
                    year = datetime.now().year
            else:
                year = datetime.now().year
            if is_vorbis:
                ffmpeg_metadata += f"{tag('date')}={year}\n"
            else:
                ffmpeg_metadata += f"{tag('year')}={year}\n"
            if session['metadata'].get('identifiers') and isinstance(session['metadata']['identifiers'], dict):
                if is_mp3 or is_mp4_like:
                    isbn = session['metadata']['identifiers'].get('isbn')
                    if isbn:
                        ffmpeg_metadata += f"{tag('isbn')}={isbn}\n"
                    asin = session['metadata']['identifiers'].get('mobi-asin')
                    if asin:
                        ffmpeg_metadata += f"{tag('asin')}={asin}\n"
            start_time = 0
            for filename, chapter_title in part_chapters:
                filepath = os.path.join(session['chapters_dir'], filename)
                duration_ms = len(AudioSegment.from_file(filepath, format=default_audio_proc_format))
                clean_title = re.sub(r'(^#)|[=\\]|(-$)', lambda m: '\\' + (m.group(1) or m.group(0)), chapter_title.replace(TTS_SML['pause'], ''))
                ffmpeg_metadata += '[CHAPTER]\nTIMEBASE=1/1000\n'
                ffmpeg_metadata += f'START={start_time}\nEND={start_time + duration_ms}\n'
                ffmpeg_metadata += f"{tag('title')}={clean_title}\n"
                start_time += duration_ms
            with open(output_metadata_path, 'w', encoding='utf-8') as f:
                f.write(ffmpeg_metadata)
            return output_metadata_path
        except Exception as e:
            error = f"generate_ffmpeg_metadata() Error: Failed to process {txt_file} → {out_file}: {e}"
            print(error)
            return False

    def export_audio(ffmpeg_combined_audio, ffmpeg_metadata_file, ffmpeg_final_file):
        try:
            if session['cancellation_requested']:
                print('Cancel requested')
                return False
            cover_path = None
            ffmpeg_cmd = [shutil.which('ffmpeg'), '-hide_banner', '-nostats', '-i', ffmpeg_combined_audio]
            if session['output_format'] == 'wav':
                ffmpeg_cmd += ['-map', '0:a', '-ar', '44100', '-sample_fmt', 's16']
            elif session['output_format'] ==  'aac':
                ffmpeg_cmd += ['-c:a', 'aac', '-b:a', '192k', '-ar', '44100']
            elif session['output_format'] == 'flac':
                ffmpeg_cmd += ['-c:a', 'flac', '-compression_level', '5', '-ar', '44100', '-sample_fmt', 's16']
            else:
                ffmpeg_cmd += ['-f', 'ffmetadata', '-i', ffmpeg_metadata_file, '-map', '0:a']
                if session['output_format'] in ['m4a', 'm4b', 'mp4', 'mov']:
                    ffmpeg_cmd += ['-c:a', 'aac', '-b:a', '192k', '-ar', '44100', '-movflags', '+faststart+use_metadata_tags']
                elif session['output_format'] == 'mp3':
                    ffmpeg_cmd += ['-c:a', 'libmp3lame', '-b:a', '192k', '-ar', '44100']
                elif session['output_format'] == 'webm':
                    ffmpeg_cmd += ['-c:a', 'libopus', '-b:a', '192k', '-ar', '48000']
                elif session['output_format'] == 'ogg':
                    ffmpeg_cmd += ['-c:a', 'libopus', '-compression_level', '0', '-b:a', '192k', '-ar', '48000']
                ffmpeg_cmd += ['-map_metadata', '1']
            ffmpeg_cmd += ['-af', 'loudnorm=I=-16:LRA=11:TP=-1.5,afftdn=nf=-70', '-strict', 'experimental', '-threads', '1', '-y', ffmpeg_final_file]
            process = subprocess.Popen(
                ffmpeg_cmd,
                env={},
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                encoding='utf-8',
                errors='ignore'
            )
            for line in process.stdout:
                print(line, end='')
            process.wait()
            if process.returncode == 0:
                if session['output_format'] in ['mp3', 'm4a', 'm4b', 'mp4']:
                    if session['cover'] is not None:
                        cover_path = session['cover']
                        msg = f'Adding cover {cover_path} into the final audiobook file...'
                        print(msg)
                        if session['output_format'] == 'mp3':
                            from mutagen.mp3 import MP3
                            from mutagen.id3 import ID3, APIC, error
                            audio = MP3(ffmpeg_final_file, ID3=ID3)
                            try:
                                audio.add_tags()
                            except error:
                                pass
                            with open(cover_path, 'rb') as img:
                                audio.tags.add(
                                    APIC(
                                        encoding=3,
                                        mime='image/jpeg',
                                        type=3,
                                        desc='Cover',
                                        data=img.read()
                                    )
                                )
                        elif session['output_format'] in ['mp4', 'm4a', 'm4b']:
                            from mutagen.mp4 import MP4, MP4Cover
                            audio = MP4(ffmpeg_final_file)
                            with open(cover_path, 'rb') as f:
                                cover_data = f.read()
                            audio["covr"] = [MP4Cover(cover_data, imageformat=MP4Cover.FORMAT_JPEG)]
                        if audio:
                            audio.save()
                final_vtt = f"{Path(ffmpeg_final_file).stem}.vtt"
                proc_vtt_path = os.path.join(session['process_dir'], final_vtt)
                final_vtt_path = os.path.join(session['audiobooks_dir'], final_vtt)
                shutil.move(proc_vtt_path, final_vtt_path)
                return True
            else:
                error = process.returncode
                print(error, ffmpeg_cmd)
                return False
        except Exception as e:
            DependencyError(e)
            return False

    try:
        session = context.get_session(id)
        _cdir = session['chapters_dir']
        chapter_files = [f for f in os.listdir(_cdir) if f.endswith(f'.{default_audio_proc_format}')]
        chapter_files = sorted(chapter_files, key=lambda x: int(re.search(r'\d+', x).group()))
        chapter_titles = [c[0] for c in session['chapters']]
        if len(chapter_files) == 0:
            print('No chapter files exists!')
            return None
        # Calculate total duration
        durations = []
        for file in chapter_files:
            filepath = os.path.join(session['chapters_dir'], file)
            durations.append(get_audio_duration(filepath))
        total_duration = sum(durations)
        exported_files = []
        if session.get('output_split'):
            part_files = []
            part_chapter_indices = []
            cur_part = []
            cur_indices = []
            cur_duration = 0
            max_part_duration = session['output_split_hours'] * 3600
            needs_split = total_duration > (int(session['output_split_hours']) * 2) * 3600
            for idx, (file, dur) in enumerate(zip(chapter_files, durations)):
                if cur_part and (cur_duration + dur > max_part_duration):
                    part_files.append(cur_part)
                    part_chapter_indices.append(cur_indices)
                    cur_part = []
                    cur_indices = []
                    cur_duration = 0
                cur_part.append(file)
                cur_indices.append(idx)
                cur_duration += dur
            if cur_part:
                part_files.append(cur_part)
                part_chapter_indices.append(cur_indices)

            for part_idx, (part_file_list, indices) in enumerate(zip(part_files, part_chapter_indices)):
                with tempfile.TemporaryDirectory() as tmpdir:
                    batch_size = 1024
                    chunk_list = []
                    for i in range(0, len(part_file_list), batch_size):
                        batch = part_file_list[i:i + batch_size]
                        txt = os.path.join(tmpdir, f'chunk_{i:04d}.txt')
                        out = os.path.join(tmpdir, f'chunk_{i:04d}.{default_audio_proc_format}')
                        with open(txt, 'w') as f:
                            for file in batch:
                                path = os.path.join(session['chapters_dir'], file).replace("\\", "/")
                                f.write(f"file '{path}'\n")
                        chunk_list.append((txt, out))
                    with Pool(cpu_count()) as pool:
                        results = pool.starmap(assemble_chunks, chunk_list)
                    if not all(results):
                        print(f"assemble_segments() One or more chunks failed for part {part_idx+1}.")
                        return None
                    # Final merge for this part
                    combined_chapters_file = os.path.join(
                        session['process_dir'],
                        f"{get_sanitized(session['metadata']['title'])}_part{part_idx+1}.{default_audio_proc_format}" if needs_split else f"{get_sanitized(session['metadata']['title'])}.{default_audio_proc_format}"
                    )
                    final_list = os.path.join(tmpdir, f'part_{part_idx+1:02d}_final.txt')
                    with open(final_list, 'w') as f:
                        for _, chunk_path in chunk_list:
                            f.write(f"file '{chunk_path.replace(os.sep, '/')}'\n")
                    if not assemble_chunks(final_list, combined_chapters_file):
                        print(f"assemble_segments() Final merge failed for part {part_idx+1}.")
                        return None

                    metadata_file = os.path.join(session['process_dir'], f'metadata_part{part_idx+1}.txt')
                    part_chapters = [(chapter_files[i], chapter_titles[i]) for i in indices]
                    generate_ffmpeg_metadata(part_chapters, session, metadata_file, default_audio_proc_format)

                    final_file = os.path.join(
                        session['audiobooks_dir'],
                        f"{session['final_name'].rsplit('.', 1)[0]}_part{part_idx+1}.{session['output_format']}" if needs_split else session['final_name']
                    )
                    if export_audio(combined_chapters_file, metadata_file, final_file):
                        exported_files.append(final_file)
        else:
            with tempfile.TemporaryDirectory() as tmpdir:
                # 1) build a single ffmpeg file list
                txt = os.path.join(tmpdir, 'all_chapters.txt')
                merged_tmp = os.path.join(tmpdir, f'all.{default_audio_proc_format}')
                with open(txt, 'w') as f:
                    for file in chapter_files:
                        path = os.path.join(session['chapters_dir'], file).replace("\\", "/")
                        f.write(f"file '{path}'\n")

                # 2) merge into one temp file
                if not assemble_chunks(txt, merged_tmp):
                    print("assemble_segments() Final merge failed.")
                    return None

                # 3) generate metadata for entire book
                metadata_file = os.path.join(session['process_dir'], 'metadata.txt')
                all_chapters = list(zip(chapter_files, chapter_titles))
                generate_ffmpeg_metadata(all_chapters, session, metadata_file, default_audio_proc_format)

                # 4) export in one go
                final_file = os.path.join(
                    session['audiobooks_dir'],
                    session['final_name']
                )
                if export_audio(merged_tmp, metadata_file, final_file):
                    exported_files.append(final_file)
        return exported_files if exported_files else None
    except Exception as e:
        DependencyError(e)
        return False

def delete_unused_tmp_dirs(web_dir, days, session):
    dir_array = [
        tmp_dir,
        web_dir,
        os.path.join(models_dir, '__sessions'),
        os.path.join(voices_dir, '__sessions')
    ]
    current_user_dirs = {
        f"proc-{session['id']}",
        f"web-{session['id']}",
        f"voice-{session['id']}",
        f"model-{session['id']}"
    }
    current_time = time.time()
    threshold_time = current_time - (days * 24 * 60 * 60)  # Convert days to seconds
    for dir_path in dir_array:
        if os.path.exists(dir_path) and os.path.isdir(dir_path):
            for dir in os.listdir(dir_path):
                if dir in current_user_dirs:        
                    full_dir_path = os.path.join(dir_path, dir)
                    if os.path.isdir(full_dir_path):
                        try:
                            dir_mtime = os.path.getmtime(full_dir_path)
                            dir_ctime = os.path.getctime(full_dir_path)
                            if dir_mtime < threshold_time and dir_ctime < threshold_time:
                                shutil.rmtree(full_dir_path, ignore_errors=True)
                                msg = f"Deleted expired session: {full_dir_path}"
                                print(msg)
                        except Exception as e:
                            error = f"Error deleting {full_dir_path}: {e}"
                            print(error)

def compare_file_metadata(f1, f2):
    if os.path.getsize(f1) != os.path.getsize(f2):
        return False
    if os.path.getmtime(f1) != os.path.getmtime(f2):
        return False
    return True
    
def get_compatible_tts_engines(language):
    compatible_engines = [
        tts for tts in models.keys()
        if language in language_tts.get(tts, {})
    ]
    return compatible_engines

def convert_ebook_batch(args, ctx=None):
    if isinstance(args['ebook_list'], list):
        ebook_list = args['ebook_list'][:]
        for file in ebook_list: # Use a shallow copy
            if any(file.endswith(ext) for ext in ebook_formats):
                args['ebook'] = file
                print(f'Processing eBook file: {os.path.basename(file)}')
                progress_status, passed = convert_ebook(args, ctx)
                if passed is False:
                    print(f'Conversion failed: {progress_status}')
                    sys.exit(1)
                args['ebook_list'].remove(file) 
        reset_ebook_session(args['session'])
        return progress_status, passed
    else:
        print(f'the ebooks source is not a list!')
        sys.exit(1)       

def convert_ebook(args, ctx=None):
    try:
        global is_gui_process, context        
        error = None
        id = None
        info_session = None
        if args['language'] is not None:
            if not os.path.splitext(args['ebook'])[1]:
                error = f"{args['ebook']} needs a format extension."
                print(error)
                return error, false
            if not os.path.exists(args['ebook']):
                error = 'File does not exist or Directory empty.'
                print(error)
                return error, false
            try:
                if len(args['language']) == 2:
                    lang_array = languages.get(part1=args['language'])
                    if lang_array:
                        args['language'] = lang_array.part3
                        args['language_iso1'] = lang_array.part1
                elif len(args['language']) == 3:
                    lang_array = languages.get(part3=args['language'])
                    if lang_array:
                        args['language'] = lang_array.part3
                        args['language_iso1'] = lang_array.part1 
                else:
                    args['language_iso1'] = None
            except Exception as e:
                pass

            if args['language'] not in language_mapping.keys():
                error = 'The language you provided is not (yet) supported'
                print(error)
                return error, false

            if ctx is not None:
                context = ctx

            is_gui_process = args['is_gui_process']
            id = args['session'] if args['session'] is not None else str(uuid.uuid4())

            session = context.get_session(id)
            session['script_mode'] = args['script_mode'] if args['script_mode'] is not None else NATIVE   
            session['ebook'] = args['ebook']
            session['ebook_list'] = args['ebook_list']
            session['device'] = args['device']
            session['language'] = args['language']
            session['language_iso1'] = args['language_iso1']
            session['tts_engine'] = args['tts_engine'] if args['tts_engine'] is not None else get_compatible_tts_engines(args['language'])[0]
            session['custom_model'] = args['custom_model'] if not is_gui_process or args['custom_model'] is None else os.path.join(session['custom_model_dir'], args['custom_model'])
            session['fine_tuned'] = args['fine_tuned']
            session['voice'] = args['voice']
            session['temperature'] =  args['temperature']
            session['length_penalty'] = args['length_penalty']
            session['num_beams'] = args['num_beams']
            session['repetition_penalty'] = args['repetition_penalty']
            session['top_k'] =  args['top_k']
            session['top_p'] = args['top_p']
            session['speed'] = args['speed']
            session['enable_text_splitting'] = args['enable_text_splitting']
            session['text_temp'] =  args['text_temp']
            session['waveform_temp'] =  args['waveform_temp']
            # session['cfg_value'] = args['cfg_value']
            # session['inference_timesteps'] = args['inference_timesteps']
            # session['normalize'] = args['normalize']
            # session['denoise'] = args['denoise']
            # session['retry_badcase'] = args['retry_badcase']
            # session['retry_badcase_max_times'] = args['retry_badcase_max_times']
            # session['retry_badcase_ratio_threshold'] = args['retry_badcase_ratio_threshold']
            session['audiobooks_dir'] = args['audiobooks_dir']
            session['output_format'] = args['output_format']
            session['output_split'] = args['output_split']    
            session['output_split_hours'] = args['output_split_hours'] if args['output_split_hours'] is not None else default_output_split_hours

            info_session = f"\n*********** Session: {id} **************\nStore it in case of interruption, crash, reuse of custom model or custom voice,\nyou can resume the conversion with --session option"

            if not is_gui_process:
                session['voice_dir'] = os.path.join(voices_dir, '__sessions', f"voice-{session['id']}", session['language'])
                os.makedirs(session['voice_dir'], exist_ok=True)
                # As now uploaded voice files are in their respective language folder so check if no wav and bark folder are on the voice_dir root from previous versions
                [shutil.move(src, os.path.join(session['voice_dir'], os.path.basename(src))) for src in glob(os.path.join(os.path.dirname(session['voice_dir']), '*.wav')) + ([os.path.join(os.path.dirname(session['voice_dir']), 'bark')] if os.path.isdir(os.path.join(os.path.dirname(session['voice_dir']), 'bark')) and not os.path.exists(os.path.join(session['voice_dir'], 'bark')) else [])]
                session['custom_model_dir'] = os.path.join(models_dir, '__sessions',f"model-{session['id']}")
                if session['custom_model'] is not None:
                    if not os.path.exists(session['custom_model_dir']):
                        os.makedirs(session['custom_model_dir'], exist_ok=True)
                    src_path = Path(session['custom_model'])
                    src_name = src_path.stem
                    if not os.path.exists(os.path.join(session['custom_model_dir'], src_name)):
                        required_files = models[session['tts_engine']]['internal']['files']
                        if analyze_uploaded_file(session['custom_model'], required_files):
                            model = extract_custom_model(session['custom_model'], session)
                            if model is not None:
                                session['custom_model'] = model
                            else:
                                error = f"{model} could not be extracted or mandatory files are missing"
                        else:
                            error = f'{os.path.basename(f)} is not a valid model or some required files are missing'
                if session['voice'] is not None:                  
                    voice_name = get_sanitized(os.path.splitext(os.path.basename(session['voice']))[0])
                    final_voice_file = os.path.join(session['voice_dir'], f'{voice_name}.wav')
                    if not os.path.exists(final_voice_file):
                        extractor = VoiceExtractor(session, session['voice'], voice_name)
                        status, msg = extractor.extract_voice()
                        if status:
                            session['voice'] = final_voice_file
                        else:
                            error = f'VoiceExtractor.extract_voice() failed! {msg}'
                            print(error)
            if error is None:
                if session['script_mode'] == NATIVE:
                    bool, e = check_programs('Calibre', 'ebook-convert', '--version')
                    if not bool:
                        error = f'check_programs() Calibre failed: {e}'
                    bool, e = check_programs('FFmpeg', 'ffmpeg', '-version')
                    if not bool:
                        error = f'check_programs() FFMPEG failed: {e}'
                if error is None:
                    old_session_dir = os.path.join(tmp_dir, f"ebook-{session['id']}")
                    session['session_dir'] = os.path.join(tmp_dir, f"proc-{session['id']}")
                    if os.path.isdir(old_session_dir):
                        os.rename(old_session_dir, session['session_dir'])
                    session['process_dir'] = os.path.join(session['session_dir'], f"{hashlib.md5(session['ebook'].encode()).hexdigest()}")
                    session['chapters_dir'] = os.path.join(session['process_dir'], "chapters")
                    session['chapters_dir_sentences'] = os.path.join(session['chapters_dir'], 'sentences')       
                    if prepare_dirs(args['ebook'], session):
                        session['filename_noext'] = os.path.splitext(os.path.basename(session['ebook']))[0]
                        msg = ''
                        msg_extra = ''
                        vram_avail = get_vram()
                        if vram_avail <= 4:
                            msg_extra += 'VRAM capacity could not be detected. -' if vram_avail == 0 else 'VRAM under 4GB - '
                            if session['tts_engine'] == TTS_ENGINES['BARK']:
                                os.environ['SUNO_USE_SMALL_MODELS'] = 'True'
                                msg_extra += f"Switching BARK to SMALL models - "
                        else:
                            if session['tts_engine'] == TTS_ENGINES['BARK']:
                                os.environ['SUNO_USE_SMALL_MODELS'] = 'False'                        
                        if session['device'] == 'cuda':
                            session['device'] = session['device'] if torch.cuda.is_available() else 'cpu'
                            if session['device'] == 'cpu':
                                msg += f"GPU not recognized by torch! Read {default_gpu_wiki} - Switching to CPU - "
                        elif session['device'] == 'mps':
                            session['device'] = session['device'] if torch.backends.mps.is_available() else 'cpu'
                            if session['device'] == 'cpu':
                                msg += f"MPS not recognized by torch! Read {default_gpu_wiki} - Switching to CPU - "
                        if session['device'] == 'cpu':
                            if session['tts_engine'] == TTS_ENGINES['BARK']:
                                os.environ['SUNO_OFFLOAD_CPU'] = 'True'
                        if default_engine_settings[TTS_ENGINES['XTTSv2']]['use_deepspeed'] == True:
                            try:
                                import deepspeed
                            except:
                                default_engine_settings[TTS_ENGINES['XTTSv2']]['use_deepspeed'] = False
                                msg_extra += 'deepseed not installed or package is broken. set to False - '
                            else: 
                                msg_extra += 'deepspeed detected and ready!'
                        if msg == '':
                            msg = f"Using {session['device'].upper()} - "
                        msg += msg_extra
                        if is_gui_process:
                            show_alert({"type": "warning", "msg": msg})
                        print(msg)
                        session['epub_path'] = os.path.join(session['process_dir'], '__' + session['filename_noext'] + '.epub')
                        if convert2epub(id):
                            epubBook = epub.read_epub(session['epub_path'], {'ignore_ncx': True})       
                            metadata = dict(session['metadata'])
                            for key, value in metadata.items():
                                data = epubBook.get_metadata('DC', key)
                                if data:
                                    for value, attributes in data:
                                        metadata[key] = value
                            metadata['language'] = session['language']
                            metadata['title'] = metadata['title'] = metadata['title'] or Path(session['ebook']).stem.replace('_',' ')
                            metadata['creator'] =  False if not metadata['creator'] or metadata['creator'] == 'Unknown' else metadata['creator']
                            session['metadata'] = metadata                  
                            try:
                                if len(session['metadata']['language']) == 2:
                                    lang_array = languages.get(part1=session['language'])
                                    if lang_array:
                                        session['metadata']['language'] = lang_array.part3
                            except Exception as e:
                                pass                         
                            if session['metadata']['language'] != session['language']:
                                error = f"WARNING!!! language selected {session['language']} differs from the EPUB file language {session['metadata']['language']}"
                                print(error)
                            session['cover'] = get_cover(epubBook, session)
                            if session['cover']:
                                session['toc'], session['chapters'] = get_chapters(epubBook, session)
                                session['final_name'] = get_sanitized(session['metadata']['title'] + '.' + session['output_format'])
                                if session['chapters'] is not None:
                                    if convert_chapters2audio(id):
                                        msg = 'Conversion successful. Combining sentences and chapters...'
                                        show_alert({"type": "info", "msg": msg})
                                        exported_files = combine_audio_chapters(id)               
                                        if exported_files is not None:
                                            chapters_dirs = [
                                                dir_name for dir_name in os.listdir(session['process_dir'])
                                                if fnmatch.fnmatch(dir_name, "chapters_*") and os.path.isdir(os.path.join(session['process_dir'], dir_name))
                                            ]
                                            shutil.rmtree(os.path.join(session['voice_dir'], 'proc'), ignore_errors=True)
                                            if is_gui_process:
                                                if len(chapters_dirs) > 1:
                                                    if os.path.exists(session['chapters_dir']):
                                                        shutil.rmtree(session['chapters_dir'], ignore_errors=True)
                                                    if os.path.exists(session['epub_path']):
                                                        os.remove(session['epub_path'])
                                                    if os.path.exists(session['cover']):
                                                        os.remove(session['cover'])
                                                else:
                                                    if os.path.exists(session['process_dir']):
                                                        shutil.rmtree(session['process_dir'], ignore_errors=True)
                                            else:
                                                if os.path.exists(session['voice_dir']):
                                                    if not any(os.scandir(session['voice_dir'])):
                                                        shutil.rmtree(session['voice_dir'], ignore_errors=True)
                                                if os.path.exists(session['custom_model_dir']):
                                                    if not any(os.scandir(session['custom_model_dir'])):
                                                        shutil.rmtree(session['custom_model_dir'], ignore_errors=True)
                                                if os.path.exists(session['session_dir']):
                                                    shutil.rmtree(session['session_dir'], ignore_errors=True)
                                            progress_status = f'Audiobook(s) {", ".join(os.path.basename(f) for f in exported_files)} created!'
                                            session['audiobook'] = exported_files[-1]
                                            print(info_session)
                                            return progress_status, True
                                        else:
                                            error = 'combine_audio_chapters() error: exported_files not created!'
                                    else:
                                        error = 'convert_chapters2audio() failed!'
                                else:
                                    error = 'get_chapters() failed!'
                            else:
                                error = 'get_cover() failed!'
                        else:
                            error = 'convert2epub() failed!'
                    else:
                        error = f"Temporary directory {session['process_dir']} not removed due to failure."
        else:
            error = f"Language {args['language']} is not supported."
        if session['cancellation_requested']:
            error = 'Cancelled'
        else:
            if not is_gui_process and id is not None:
                error += info_session
        print(error)
        return error, False
    except Exception as e:
        print(f'convert_ebook() Exception: {e}')
        return e, False

def restore_session_from_data(data, session):
    try:
        for key, value in data.items():
            if key in session:  # Check if the key exists in session
                if isinstance(value, dict) and isinstance(session[key], dict):
                    restore_session_from_data(value, session[key])
                else:
                    session[key] = value
    except Exception as e:
        DependencyError(e)

def reset_ebook_session(id):
    session = context.get_session(id)
    data = {
        "ebook": None,
        "chapters_dir": None,
        "chapters_dir_sentences": None,
        "epub_path": None,
        "filename_noext": None,
        "chapters": None,
        "cover": None,
        "status": None,
        "progress": 0,
        "duration": 0,
        "playback_time": 0,
        "cancellation_requested": False,
        "event": None,
        "metadata": {
            "title": None, 
            "creator": None,
            "contributor": None,
            "language": None,
            "identifier": None,
            "publisher": None,
            "date": None,
            "description": None,
            "subject": None,
            "rights": None,
            "format": None,
            "type": None,
            "coverage": None,
            "relation": None,
            "Source": None,
            "Modified": None
        }
    }
    restore_session_from_data(data, session)
