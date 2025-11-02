import os
import pytest
from ebooklib import epub

from lib import TTS_ENGINES, tmp_dir, voices_dir
from lib.classes.tts_engines.coqui import Coqui
from lib.classes.tts_manager import TTSManager
from lib.epub import EPubProcessor
from lib.headless_processor import EBookProcessor
from lib.session import SessionContextMock


@pytest.fixture
def tmp_path():
    return os.path.abspath('tmp')

@pytest.fixture
def ebook_path():
    return os.path.abspath('ebooks')

@pytest.fixture
def session_context(tmp_path):
    """Fixture to create a temporary session context for tests."""

    # # Create necessary directories
    # process_dir = os.path.join(tmp_path,  "test_process")
    # os.makedirs(process_dir, exist_ok=True)
    # session['process_dir'] = str(process_dir)

    session_id = "test-session"
    context = SessionContextMock(
        {
            "session": session_id,
            'cancellation_requested': False,
            # "ebook": os.path.join(ebook_path, "UnravelMe-c12.epub"),
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
            # "speaker_wav": os.path.join(voices_dir, "zho", "adult", "male", "yunjian_24000.wav"),
            "temperature": 0.75,
            "length_penalty": 1.0,
            "num_beams": 5,
            "repetition_penalty": 1.0,
            "top_k": 50,
            "top_p": 0.95,
            "speed": 1.0,
            "enable_text_splitting": True,
            "text_temp": 0.7,
            "waveform_temp": 0.7,
            "audiobooks_dir": tmp_path,
            "output_split": "by-chapter",
            "output_split_hours": 1,
            "is_gui_process": False,
            "script_mode": "native"
        }
    )
    session = context.get_session(session_id)


    return context, session_id, session



def test_tts_cn_convert(session_context, ebook_path, tmp_path):
    context, session_id, session = session_context
    # own process dir
    process_dir = os.path.join(tmp_path,  "test_god_c12")
    os.makedirs(process_dir, exist_ok=True)
    session['process_dir'] = str(process_dir)

    # Setup arguments for EBookProcessor
    args = {
        "ebook": os.path.join(ebook_path, "god-c12.epub"),
        "chapters_dir": os.path.join(session['process_dir'], "chapters"),
        "chapters_dir_sentences": os.path.join(session['process_dir'], "chapters", "sentences"),
        "device": "cpu",
        "language": "zho",
        "language_iso1": "zh",
        "tts_engine": TTS_ENGINES['XTTSv2'],
        "voice": None,
        "voice_dir": os.path.join(voices_dir, '__sessions', "test_voice"),
        "speaker_wav": os.path.join(voices_dir, "zho", "adult", "male", "yunjian_24000.wav"),
    }
    # update session with args
    session.update(args)
    os.makedirs(session['chapters_dir'], exist_ok=True)
    os.makedirs(session['chapters_dir_sentences'], exist_ok=True)

    # Instantiate EBookProcessor
    ebook_processor = EBookProcessor()
    session["epub_path"] = session["ebook"]
    epubBook = epub.read_epub(session["ebook"], {"ignore_ncx": True})
    basename = os.path.basename(session["ebook"])
    name_splits = os.path.splitext(basename)
    session["filename_noext"] = name_splits[0]

    # Process the EPUB
    status, success = ebook_processor.process_epub_chapters(epubBook, session)

    # Assertions
    assert success is True
    print(session['audiobook'])
    assert os.path.exists(session['audiobook'])

def test_tts_en_convert(session_context, ebook_path, tmp_path):
    context, session_id, session = session_context
    # Create necessary directories
    process_dir = os.path.join(tmp_path,  "test_UnravelMe-c12")
    os.makedirs(process_dir, exist_ok=True)
    session['process_dir'] = str(process_dir)

    # Setup arguments for EBookProcessor
    args = {
        "ebook": os.path.join(ebook_path, "UnravelMe-c12.epub"),
        "chapters_dir": os.path.join(session['process_dir'], "chapters"),
        "chapters_dir_sentences": os.path.join(session['process_dir'], "chapters", "sentences"),
        "device": "cpu",
        "language": "eng",
        "language_iso1": "en",
        "tts_engine": TTS_ENGINES['XTTSv2'],
        # "speaker_wav": os.path.join(voices_dir, "zho", "adult", "male", "yunjian_24000.wav"),
        "final_name": 'one-sentense.flac'
    }
    # update session with args
    session.update(args)
    os.makedirs(session['chapters_dir'], exist_ok=True)
    os.makedirs(session['chapters_dir_sentences'], exist_ok=True)

    # Instantiate EBookProcessor
    # ebook_processor = EBookProcessor()
    # session["epub_path"] = session["ebook"]
    # epubBook = epub.read_epub(session["ebook"], {"ignore_ncx": True})
    # basename = os.path.basename(session["ebook"])
    # name_splits = os.path.splitext(basename)
    # session["filename_noext"] = name_splits[0]

    tts_manager = TTSManager(session)
    result = tts_manager.convert_sentence2audio(1, "Compute or retrieve speaker latents.")
    assert result
