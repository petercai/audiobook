import inspect
import os

import pytest
from ebooklib import epub
from lib.lang import year_to_decades_languages
from lib.models import TTS_ENGINES
from lib.conf import voices_dir, models_dir
from lib.epub import EPubProcessor
from lib.epub_creator import EPubCreator
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
            "output_split": True,
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

def test_convert2epub(session_context, ebook_path, tmp_path):
    """Test successful conversion of a .txt or .pdf file to .epub."""
    context, session_id, session = session_context
    # session = context.get_session(session_id)
    # Create necessary directories
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)

    input_file = os.path.join(ebook_path, "Dune.epub")

    session['ebook'] = str(input_file)
    session['epub_path'] = tmp_path+  "/book_gen.epub"

    creator = EPubCreator()
    result = creator.convert2epub(session)

def test_process_epub_cn(session_context, ebook_path, tmp_path):
    """Test successful processing of an EPUB file."""
    context, session_id, session = session_context

    # Setup arguments for EBookProcessor
    args = {
        "ebook": os.path.join(ebook_path, "god-c12.epub"),
        "device": "cpu",
        "language": "zho",
        "language_iso1": "zh",
        "tts_engine": TTS_ENGINES['VOXCPM'],
        "voice_dir": os.path.join(voices_dir, '__sessions', "test_voice"),
        "speaker_wav": os.path.join(voices_dir, "zho", "adult", "male", "yunjian.wav"),
        # "enable_text_splitting": True,
        "output_format": "mb4",
    }
    # update session with args
    session.update(args)
    # Create necessary directories
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    session['epub_path'] = session['ebook']
    
    basename = os.path.basename(session["ebook"])
    name_splits = os.path.splitext(basename)
    session["filename_noext"] = name_splits[0]

    # Instantiate EBookProcessor
    from lib.ebook_processor import EBookProcessor
    ebook_processor = EBookProcessor()
    # Process the EPUB
    status, success = ebook_processor.process_ebook(session)

    # Assertions
    print(status)
    assert success
    assert "Audiobook(s)" in status
    assert os.path.exists(session['audiobook'])
    
def test_process_epub_en(session_context, ebook_path, tmp_path):
    """Test successful processing of an EPUB file."""
    context, session_id, session = session_context

    # Setup arguments for EBookProcessor
    args = {
        "ebook": os.path.join(ebook_path, "jane-eyre-c12.epub"),
        "device": "cpu",
        
        "language_iso1": "en",
        "tts_engine": TTS_ENGINES['XTTSv2'],
        "output_format": "m4b",
        "offline_mode": True
    }
    # update session with args
    session.update(args)
    # Create necessary directories
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    session['epub_path'] = session['ebook']

    basename = os.path.basename(session["ebook"])
    name_splits = os.path.splitext(basename)
    session["filename_noext"] = name_splits[0]

    # Instantiate EBookProcessor
    from lib.ebook_processor import EBookProcessor
    ebook_processor = EBookProcessor()
    # Process the EPUB
    status, success = ebook_processor.process_ebook(session)

    # Assertions
    assert success is True
    assert "Audiobook(s)" in status
    assert os.path.exists(session['audiobook'])

def test_process_epub_en_mps(session_context, ebook_path, tmp_path):
    """Test successful processing of an EPUB file."""
    context, session_id, session = session_context

    # Setup arguments for EBookProcessor
    args = {
        "ebook": os.path.join(ebook_path, "jane-eyre-c12.epub"),
        "device": "mps",
        
        "language_iso1": "en",
        "tts_engine": TTS_ENGINES['XTTSv2'],
        "output_format": "m4b",
        "offline_mode": True
    }
    # update session with args
    session.update(args)
    # Create necessary directories
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    session['epub_path'] = session['ebook']

    basename = os.path.basename(session["ebook"])
    name_splits = os.path.splitext(basename)
    session["filename_noext"] = name_splits[0]

    # Instantiate EBookProcessor
    from lib.ebook_processor import EBookProcessor
    ebook_processor = EBookProcessor()
    # Process the EPUB
    status, success = ebook_processor.process_ebook(session)

    # Assertions
    assert success is True
    assert "Audiobook(s)" in status
    assert os.path.exists(session['audiobook'])

def test_process_epub_chapters_cn(session_context, ebook_path, tmp_path):
    """Test successful processing of an EPUB file."""
    context, session_id, session = session_context

    # Setup arguments for EBookProcessor
    args = {
        "ebook": os.path.join(ebook_path, "god-c12.epub"),
        "ebook_list": None,
        "device": "cpu",
        "language": "zho",
        "language_iso1": "zh",
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
    epubBook = epub.read_epub(session["ebook"], {"ignore_ncx": True})
    basename = os.path.basename(session["ebook"])
    name_splits = os.path.splitext(basename)
    session["filename_noext"] = name_splits[0]

    # Process the EPUB
    status, success = ebook_processor.process_epub_by_chapters(epubBook, session)

    # Assertions
    assert success is True
    print(session['audiobook'])
    assert os.path.exists(session['audiobook'])

def test_process_epub_by_chapters_en1(session_context, ebook_path, tmp_path):
    """Test successful processing of an EPUB file."""
    context, session_id, session = session_context
    args = {
        "ebook": os.path.join(ebook_path, "English-1.epub"),
        "ebook_list": None,
        "device": "mps",
        "language": "eng",
        "language_iso1": "en",
        "tts_engine": TTS_ENGINES['XTTSv2'],
        "output_format": "mp4",
        "offline_mode": True,
    }
    # update session with args
    session.update(args)
    
    # Create necessary directories
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    session['epub_path'] = session['ebook']
    basename = os.path.basename(session["ebook"])
    name_splits = os.path.splitext(basename)
    session["filename_noext"] = name_splits[0]

    # Instantiate EBookProcessor
    from lib.ebook_processor import EBookProcessor
    ebook_processor = EBookProcessor()
    epubBook = epub.read_epub(session["ebook"], {"ignore_ncx": True})

    # Process the EPUB
    status, success = ebook_processor.process_epub_by_chapters(epubBook, session)

    # Assertions
    assert success is True
    print(session['audiobook'])
    assert os.path.exists(session['audiobook'])
    
def test_process_epub_by_chapters_en2(session_context, ebook_path, tmp_path):
    """Test successful processing of an EPUB file."""
    context, session_id, session = session_context
    args = {
        "ebook": os.path.join(ebook_path, "English-2.epub"),
        "ebook_list": None,
        "device": "mps",
        "language": "eng",
        "language_iso1": "en",
        "tts_engine": TTS_ENGINES['XTTSv2'],
        "output_format": "mp4",
        "offline_mode": True,
    }
    # update session with args
    session.update(args)
    
    # Create necessary directories
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    session['epub_path'] = session['ebook']
    basename = os.path.basename(session["ebook"])
    name_splits = os.path.splitext(basename)
    session["filename_noext"] = name_splits[0]

    # Instantiate EBookProcessor
    from lib.ebook_processor import EBookProcessor
    ebook_processor = EBookProcessor()
    epubBook = epub.read_epub(session["ebook"], {"ignore_ncx": True})

    # Process the EPUB
    status, success = ebook_processor.process_epub_by_chapters(epubBook, session)

    # Assertions
    assert success is True
    print(session['audiobook'])
    assert os.path.exists(session['audiobook'])
    
def test_process_epub_by_chapters_jane_eyre_c5(session_context, ebook_path, tmp_path):
    """Test successful processing of an EPUB file."""
    context, session_id, session = session_context
    args = {
        "ebook": os.path.join(ebook_path, "Jan-Eyre-5.epub"),
        "ebook_list": None,
        "device": "mps",
        "language": "eng",
        "language_iso1": "en",
        "tts_engine": TTS_ENGINES['XTTSv2'],
        "output_format": "mp4",
        "add_toc_title": False,
        "offline_mode": False,
    }
    # update session with args
    session.update(args)
    
    # Create necessary directories
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    session['epub_path'] = session['ebook']
    basename = os.path.basename(session["ebook"])
    name_splits = os.path.splitext(basename)
    session["filename_noext"] = name_splits[0]

    # Instantiate EBookProcessor
    from lib.ebook_processor import EBookProcessor
    ebook_processor = EBookProcessor()
    epubBook = epub.read_epub(session["ebook"], {"ignore_ncx": True})

    # Process the EPUB
    status, success = ebook_processor.process_epub_by_chapters(epubBook, session)

    # Assertions
    assert success is True
    print(session['audiobook'])
    assert os.path.exists(session['audiobook'])
