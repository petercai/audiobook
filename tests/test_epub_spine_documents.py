import os

import pytest
from ebooklib import epub
from lib.lang import year_to_decades_languages
from lib.models import TTS_ENGINES
from lib.conf import voices_dir, models_dir
from lib.epub import EPubProcessor
from lib.mock_session import SessionContextMock, set_process_dir

import sys

from syntrive.adapters.text.normalizer import TextNormalizer
sys.stdout.reconfigure(encoding="utf-8")

@pytest.fixture
def tmp_path():
    return os.path.abspath('tmp')

@pytest.fixture
def ebook_path():
    return os.path.abspath('ebooks')

@pytest.fixture
def session_context(tmp_path: str):
    """Fixture to create a temporary session context for tests."""
    session_id = "test-session"
    context = SessionContextMock(
        {
            "session": session_id,
            'cancellation_requested': False,
            # "ebook": os.path.join(ebook_path, "jane-eyre-c12.epub"),
            # "chapters_dir": os.path.join(process_dir, "chapters"),
            # "chapters_dir_sentences": os.path.join(process_dir, "chapters", "sentences"),
            "ebook_list": None,
            "device": "cpu",
            
            "language_iso1": "en",
            "tts_engine": TTS_ENGINES['XTTSv2'],
            "output_format": "m4b",
            "custom_model": None,
            "fine_tuned": "internal",
            "voice": None,
            "voice_dir": os.path.join(voices_dir, '__sessions', "test_voice"),
            "speaker_wav": os.path.join(voices_dir, "zho", "adult", "male", "yunjian.wav"),
            # "temperature": 0.75,
            # "length_penalty": 1.0,
            # "num_beams": 5,
            # "repetition_penalty": 1.0,
            # "top_k": 50,
            # "top_p": 0.95,
            # "speed": 1.0,
            "enable_text_splitting": True,
            # "text_temp": 0.7,
            # "waveform_temp": 0.7,
            "audiobooks_dir": tmp_path,
            "output_split": "by-chapter",
            "output_split_minutes": 30,
            "is_gui_process": False,
            "script_mode": "native",
            "offline_mode": False,
        "metadata": {
            "title": "", 
            "creator": "",
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
        }
        }
    )
    session = context.get_session(session_id)
    return context, session_id, session


def test_extract_chapter_思考快与慢(session_context, ebook_path: str, tmp_path: str):
    context, session_id, session = session_context
    args = {
        "session": session_id,
        'cancellation_requested': False,
        "ebook": os.path.join(ebook_path, "思考,快与慢.epub"),
        "device": "cpu",
        "language_iso1": 'zh',
        "tts_engine": TTS_ENGINES['XTTSv2'],

    }
    # update session with args
    session.update(args)
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    handle_epub_chapters_in_test(session) 

def test_extract_chapter_剑来(session_context, ebook_path: str, tmp_path: str):
    context, session_id, session = session_context
    args = {
        "session": session_id,
        'cancellation_requested': False,
        "ebook": os.path.join(ebook_path, "剑来 (烽火戏诸侯).epub"),
        "device": "cpu",
        "language_iso1": 'zh',
        "tts_engine": TTS_ENGINES['XTTSv2'],

    }
    # update session with args
    session.update(args)
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    handle_epub_chapters_in_test(session) 




def test_extract_chapter_一句顶一万句(session_context, ebook_path: str, tmp_path: str):
    context, session_id, session = session_context
    args = {
        "session": session_id,
        'cancellation_requested': False,
        "ebook": os.path.join(ebook_path, "一句顶一万句 (刘震云).epub"),
        "device": "cpu",
        "language_iso1": 'zh',
        "tts_engine": TTS_ENGINES['XTTSv2'],

    }
    # update session with args
    session.update(args)
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    handle_epub_chapters_in_test(session) 
    
def test_extract_chapter_4_dune(session_context, ebook_path: str, tmp_path: str):
    context, session_id, session = session_context
    args = {
        "session": session_id,
        'cancellation_requested': False,
        "ebook": os.path.join(ebook_path, "Dune.epub"),
        "device": "cpu",
        
        "language_iso1": 'en',
        "tts_engine": TTS_ENGINES['XTTSv2'],

    }
    # update session with args
    session.update(args)
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    handle_epub_chapters_in_test(session) 
    
def test_extract_chapter__Grea_Power_Politics(session_context, ebook_path: str, tmp_path: str):
    context, session_id, session = session_context
    args = {
        "session": session_id,
        'cancellation_requested': False,
        "ebook": os.path.join(ebook_path, "The Tragedy of Great Power Politics.epub"),
        "device": "cpu",
        
        "language_iso1": 'en',
        "tts_engine": TTS_ENGINES['XTTSv2'],

    }
    # update session with args
    session.update(args)
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    handle_epub_chapters_in_test(session) 
    
def test_extract_chapter_4_hunger_game(session_context, ebook_path: str, tmp_path: str):
    context, session_id, session = session_context
    args = {
        "session": session_id,
        'cancellation_requested': False,
        "ebook": os.path.join(ebook_path, "The Hunger Games-2008 - The Hunger Games (Suzanne Collins) .epub"),
        "device": "cpu",
        
        "language_iso1": 'en',
        "tts_engine": TTS_ENGINES['XTTSv2'],

    }
    # update session with args
    session.update(args)
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    handle_epub_chapters_in_test(session) 


def cache_text_in_dir(base_name, tuple_lines, cache_dir):
    cache_path = os.path.join(cache_dir, f"{base_name}.txt")
    with open(cache_path, "w", encoding="utf-8") as cache_file:
        cache_file.writelines(
            f"{a}: {b}\n" for a, b in tuple_lines
        )


def handle_epub_chapters_in_test(session):
    ebook_ = session["ebook"]
    epubBook = epub.read_epub(ebook_, {"ignore_ncx": True})   
    processor = EPubProcessor(session)
    processor.text_normalizer = TextNormalizer(session['language_iso1'])
    epub_chapter_docs, toc = processor.get_epub_chapters(epubBook)
    print(f"epub_chapter_docs#: {len(epub_chapter_docs)}")
    cache_dir = os.path.join(session["process_dir"], "extracted")
    os.makedirs(cache_dir, exist_ok=True)
    for c_doc in epub_chapter_docs:
        chapter_id = getattr(c_doc, "id", None)
        chapter_media_type = getattr(c_doc, "media_type", None)
        paragraphes = processor.extract_chapter_tagged_paragraphes(c_doc, False)
        if paragraphes:
            print(c_doc, chapter_id, chapter_media_type)
            cache_text_in_dir(chapter_id, paragraphes, cache_dir)
        else:
            print (f"{c_doc} - no content")