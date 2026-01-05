import inspect
import os

import pytest
from ebooklib import epub
from lib.lang import year_to_decades_languages
from lib.models import TTS_ENGINES
from lib.conf import voices_dir, models_dir
from lib.epub import EPubProcessor
from lib.mock_session import SessionContextMock, set_process_dir

import sys

from lib.util import util
from syntrive.adapters.text.normalizer import TextNormalizer
sys.stdout.reconfigure(encoding="utf-8")

@pytest.fixture
def tmp_path():
    return os.path.abspath('tmp')

@pytest.fixture
def ebook_path():
    return os.path.abspath('ebooks')

@pytest.fixture
def book_context():
    bookname = '纯真年代(伊迪丝华顿) .epub'
    bookname = '思考,快与慢.epub'
    bookname = '剑来 (烽火戏诸侯).epub'
    bookname = '一句顶一万句 (刘震云).epub'
    title = util.sanitize_filename(bookname.split('.')[0])
    pipeline = f"PROCESSING-{title}"  
    return bookname, title, pipeline



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
            "language": "eng",
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



def test_process_epub_metadata_cn(session_context, ebook_path, tmp_path):
    context, session_id, session = session_context
    # Setup arguments for EBookProcessor
    args = {
        "session": session_id,
        'cancellation_requested': False,
        "ebook": os.path.join(ebook_path, "god-c12.epub"),
        "device": "cpu",
        "language": "zho",
        "language_iso1": 'zh',
        "tts_engine": TTS_ENGINES['VOXCPM'],
        "output_format": "m4b",
    }
    # update session with args
    session.update(args)
    # Create necessary directories
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    session['epub_path'] = session['ebook']
    # Instantiate EBookProcessor
    from lib.ebook_processor import EBookProcessor
    ebook_processor = EBookProcessor()
    epubBook = epub.read_epub(session["epub_path"], {"ignore_ncx": True})
    basename = os.path.basename(session["ebook"])
    name_splits = os.path.splitext(basename)
    session["filename_noext"] = name_splits[0]
    # Process the EPUB
    status, success = ebook_processor.split_epub_by_chapter(session, epubBook)
    # Assertions
    assert success is True
    metadata = session['metadata']
    # print dict metadata
    for key, value in metadata.items():
        print(f"{key}: {value}")

def test_process_epub_metadata_en(session_context, ebook_path, tmp_path):
    context, session_id, session = session_context
    # Setup arguments for EBookProcessor
    args = {
        "session": session_id,
        'cancellation_requested': False,
        "ebook": os.path.join(ebook_path, "Dune.epub"),
        "device": "cpu",
        "language_iso1": 'en',
        "tts_engine": TTS_ENGINES['XTTSv2'],
        "output_format": "m4b",
    }
    # update session with args
    session.update(args)
    # Create necessary directories
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    session['epub_path'] = session['ebook']
    # Instantiate EBookProcessor
    from lib.ebook_processor import EBookProcessor
    ebook_processor = EBookProcessor()
    epubBook = epub.read_epub(session["epub_path"], {"ignore_ncx": True})
    basename = os.path.basename(session["ebook"])
    name_splits = os.path.splitext(basename)
    session["filename_noext"] = name_splits[0]
    # Process the EPUB
    status, success = ebook_processor.split_epub_by_chapter(session, epubBook)
    # Assertions
    assert success is True
    metadata = session['metadata']
    # print dict metadata
    for key, value in metadata.items():
        print(f"{key}: {value}")

def test_show_chapters_and_sentences_en(session_context, ebook_path, tmp_path):
    context, session_id, session = session_context
    # Setup arguments for EBookProcessor
    args = {
        "ebook": os.path.join(ebook_path, "jane-eyre-c12.epub"),
        "device": "cpu",
        
        "language_iso1": 'en',
        "tts_engine": TTS_ENGINES['XTTSv2'],
    }

    # update session with args
    session.update(args)

    ebook_ = session["ebook"]
    epubBook = epub.read_epub(ebook_, {"ignore_ncx": True})

    processor = EPubProcessor(session)
    toc, chapters = processor.get_chapters_in_sentences(epubBook, session)
    # Assertions
    assert toc
    print(toc)
    assert chapters
    for chapter in chapters:
        for i, sentence in enumerate(chapter, 1):
            print(f"{i}: {sentence}")

def test_get_chapters_cn(session_context, ebook_path, tmp_path):
    context, session_id, session = session_context
    # Setup arguments for EBookProcessor
    args = {
        "ebook": os.path.join(ebook_path, "god-c12.epub"),
        "device": "cpu",
        "language": "zho",
        "language_iso1": 'zh',
        "tts_engine": TTS_ENGINES['VOXCPM'],
    }

    # update session with args
    session.update(args)

    ebook_ = session["ebook"]
    epubBook = epub.read_epub(ebook_, {"ignore_ncx": True})

    processor = EPubProcessor(session)
    toc, chapters = processor.get_chapters_in_sentences(epubBook, session)
    # Assertions
    assert toc
    print(toc)
    assert chapters
    for chapter in chapters:
        for i, sentence in enumerate(chapter, 1):
            print(f"{i}: {sentence}")


def test_get_book_cover(session_context, ebook_path, book_context):
    context, session_id, session = session_context
    bookname, title, pipeline = book_context
    args = {
        "session": session_id,
        'cancellation_requested': False,
        "ebook": os.path.join(ebook_path, bookname),
        "filename_noext": title,
        "device": "cpu",
        "language": "zho",
        "language_iso1": 'zh',
        "tts_engine": TTS_ENGINES['XTTSv2'],
    }

    # update session with args
    session.update(args)
    # Create necessary directories
    set_process_dir(session, pipeline)
    
    ebook_ = session["ebook"]
    epubBook = epub.read_epub(ebook_, {"ignore_ncx": True})
    path = session['process_dir']
    cover_name = session['filename_noext']
    processor = EPubProcessor(session)
    result = processor.extract_book_cover(epubBook, path, cover_name)
    # Assertions
    assert result
    print(result)
    
def test_retrieve_book_image(session_context, ebook_path, book_context):
    context, session_id, session = session_context
    bookname, title, pipeline = book_context
    # Setup arguments for EBookProcessor
    args = {
        "session": session_id,
        'cancellation_requested': False,
        "ebook": os.path.join(ebook_path, bookname),
        "filename_noext": title,
        "device": "cpu",
        "language": "zho",
        "language_iso1": 'zh',
        "tts_engine": TTS_ENGINES['XTTSv2'],
    }

    # update session with args
    session.update(args)
    # Create necessary directories
    set_process_dir(session, pipeline)
    
    ebook_ = session["ebook"]
    epubBook = epub.read_epub(ebook_, {"ignore_ncx": True})
    path = session['process_dir']
    processor = EPubProcessor(session)
    result = processor.extract_book_images(epubBook, path)
    assert result
    for file in result:
        print(file)


def test_split_epub_by_chapter(session_context, ebook_path):
    context, session_id, session = session_context
    book_filename = "jane-eyre-c12.epub"
    book_name = book_filename.split(".")[0]  
    args = {
        "session": session_id,
        "cancellation_requested": False,
        "ebook": os.path.join(ebook_path, book_filename),
        "device": "cpu",
        "add_toc_title": True,
        "language_iso1": "en",
        "tts_engine": TTS_ENGINES["XTTSv2"],
        "filename_noext": book_name
    }
    # update session with args
    session.update(args)
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    
    ebook_ = session["ebook"]
    epubBook = epub.read_epub(ebook_, {"ignore_ncx": True})
    from lib.ebook_processor import EBookProcessor
    processor = EBookProcessor()
    status, success = processor.split_epub_by_chapter(session, epubBook)
    assert success
