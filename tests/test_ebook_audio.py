
import inspect
import os
import pytest
from ebooklib import epub

from lib import TTS_ENGINES, tmp_dir, voices_dir
from lib.ebook_audio import EbookAudio
from lib.epub import EPubProcessor
from lib.headless_processor import EBookProcessor
from lib.mock_session import SessionContextMock, set_process_dir

import sys
sys.stdout.reconfigure(encoding="utf-8")

@pytest.fixture
def tmp_path():
    return os.path.abspath('tmp')

@pytest.fixture
def ebook_path():
    return os.path.abspath('ebooks')

@pytest.fixture
def session_context(tmp_path):
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


    
def test_combine_audio_chapters(session_context, ebook_path, tmp_path):
    """Test successful processing of an EPUB file."""
    context, session_id, session = session_context

    # Setup arguments for EBookProcessor
    args = {
        "session": "34580d40b4f8e9a591f0ee19dc51a4f4",
        "ebook": os.path.join(ebook_path, "jane-eyre-c12.epub"),
        "device": "cpu",
        "language": "eng",
        "language_iso1": "en",
        "tts_engine": TTS_ENGINES['XTTSv2'],
        "output_format": "mp4",
        "chapters": [
                        ["chapter_1.flac"],
                        ["chapter_2.flac"],
                        ["chapter_3.flac"],
                        ["chapter_4.flac"],
                        ["chapter_5.flac"],
                        ["chapter_6.flac"],
                        ["chapter_7.flac"],
                        ["chapter_8.flac"],
                        ["chapter_9.flac"],
                        ["chapter_10.flac"],
                        ["chapter_11.flac"],
                        ["chapter_12.flac"],
                        ["chapter_13.flac"],
                        ["chapter_14.flac"],
                        ["chapter_15.flac"],
                        ["chapter_16.flac"],
                        ["chapter_17.flac"],
                        ["chapter_18.flac"],
                        ["chapter_19.flac"],
                        ["chapter_20.flac"],
                        ["chapter_21.flac"],
                        ["chapter_22.flac"],
                        ["chapter_23.flac"],
                        ["chapter_24.flac"],
                        ["chapter_25.flac"],
                        ["chapter_26.flac"],
                        ["chapter_27.flac"],
                        ["chapter_28.flac"],
                        ["chapter_29.flac"],
                        ["chapter_30.flac"],
                ],
        "output_split": True,
        "output_split_minutes": 30,
        "final_name": "Hunger_Games_01_-_The_Hunger_Games",
        "offline_mode": True
    }
    # update session with args
    session.update(args)
    # Create necessary directories
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, "Hunger_Games_01_-_The_Hunger_Games/Hunger_Games_01_-_The_Hunger_Games")
    session['epub_path'] = session['ebook']
    session['cover'] = os.path.join(session['process_dir'], 'The Hunger Games-2008 - The Hunger Games Suzanne Collins .jpg')

    basename = os.path.basename(session["ebook"])
    name_splits = os.path.splitext(basename)
    session["filename_noext"] = name_splits[0]

    # Instantiate EBookProcessor
    processor = EbookAudio()
    # Process the EPUB
    audio_files = processor.combine_audio_chapters(session)

    # Assertions
    # assert audio_files
    for file in audio_files:
        print(file)

def test_stamp_on_image(session_context, ebook_path, tmp_path):
    """Test successful processing of an EPUB file."""
    context, session_id, session = session_context

    # Setup arguments for EBookProcessor
    args = {
        "session": "34580d40b4f8e9a591f0ee19dc51a4f4",
        "ebook": os.path.join(ebook_path, "The_Hunger_Games.epub"),
        "device": "cpu",
        "language": "eng",
        "language_iso1": "en",
        "tts_engine": TTS_ENGINES['XTTSv2'],
        "output_format": "mp4",
        "output_split": True,
        "output_split_minutes": 30,
        "final_name": "Hunger_Games_01_-_The_Hunger_Games",
        "offline_mode": True
    }
    # update session with args
    session.update(args)
    # Create necessary directories
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, "Hunger_Games_01_-_The_Hunger_Games/Hunger_Games_01_-_The_Hunger_Games")
    session['epub_path'] = session['ebook']
    session['cover'] = os.path.join(session['process_dir'], 'The Hunger Games-2008 - The Hunger Games Suzanne Collins .jpg')

    basename = os.path.basename(session["ebook"])
    name_splits = os.path.splitext(basename)
    session["filename_noext"] = name_splits[0]
    new_cover = os.path.join(tmp_dir, f"{basename}_part{1:02d}.jpg")

    # Instantiate EBookProcessor
    processor = EbookAudio()
    with open( session['cover'], 'rb') as f:
        cover_data = f.read()
        cover_data = processor.stamp_on_image_data(cover_data, str(1))
        with open(new_cover, "wb") as wf:
            wf.write(cover_data)

