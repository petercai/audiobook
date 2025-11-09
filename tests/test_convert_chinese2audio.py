import inspect
import os
import shutil
import pytest
from lib.epub import EPubProcessor
from lib.functions import *
from lib.conf import *
from lib.mock_session import SessionContextMock, set_process_dir
from lib.models import *


@pytest.fixture
def test_session():
    # Initialize a session context for testing
    session_id = "test-session"
    context = SessionContextMock(
        {
            "script_mode": "native",
            "id": session_id,
            "process_id": None,
            "device": 'cpu',
            "system": None,
            "client": None,
            "language": 'eng',
            "language_iso1": "en",
            "audiobook": None,
            "audiobooks_dir": os.path.join(tmp_dir, "test_audiobooks"),
            "process_dir": os.path.join(tmp_dir, "test_process"),
            "ebook": None,
            "ebook_list": None,
            "ebook_mode": "single",
            "chapters_dir": os.path.join(tmp_dir, "test_process", "chapters"),
            "chapters_dir_sentences": os.path.join(tmp_dir, "test_process", "chapters", "sentences"),
            "epub_path": None,
            "filename_noext": None,
            "tts_engine": 'xtts',
            "fine_tuned": 'internal',
            "voice": None,
            "voice_dir": os.path.join(voices_dir, '__sessions', "test_voice"),
            "speaker_wav": os.path.join(voices_dir, "eng", "adult", "female", "AlexandraHisakawa_24000.wav"),
            "custom_model": None,
            "custom_model_dir": os.path.join(models_dir, '__sessions', "test_model"),
            "toc": None,
            "chapters": None,
            "cover": None,
            "status": None,
            "progress": 0,
            "time": None,
            "cancellation_requested": False,
            # "temperature": default_xtts_settings['temperature'],
            # "length_penalty": default_xtts_settings['length_penalty'],
            # "num_beams": default_xtts_settings['num_beams'],
            # "repetition_penalty": default_xtts_settings['repetition_penalty'],
            # "top_k": default_xtts_settings['top_k'],
            # "top_p": default_xtts_settings['top_p'],
            # "speed": default_xtts_settings['speed'],
            # "enable_text_splitting": default_xtts_settings['enable_text_splitting'],
            # "text_temp": default_bark_settings['text_temp'],
            # "waveform_temp": default_bark_settings['waveform_temp'],
            "event": None,
            "final_name": None,
            "output_format": 'wav',
            "metadata": {
                "title": "Test Audiobook",
                "creator": "Test Author",
                "contributor": None,
                "language": 'eng',
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
        })
    session = context.get_session(session_id)

    # Create necessary directories
    os.makedirs(session['audiobooks_dir'], exist_ok=True)
    os.makedirs(session['process_dir'], exist_ok=True)
    os.makedirs(session['chapters_dir'], exist_ok=True)
    os.makedirs(session['chapters_dir_sentences'], exist_ok=True)
    os.makedirs(session['custom_model_dir'], exist_ok=True)
    os.makedirs(session['voice_dir'], exist_ok=True)

    return context, session_id, session


def test_convert_chinese2audio(test_session):
    context, session_id, session = test_session
    # Read test file content
    test_file_path = "ebooks/god-1.txt"
    with open(test_file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split content into chapters for testing (assuming chapters are separated by some delimiter, here using empty line for simplicity)
    chapters = content.split('\n\n')
    chapter_strip_ = chapter_strip_ = [
            re.split(r'[。，]', chapter)   # split on either 。 or ，
            for chapter in chapters
            if chapter.strip()            # filter out empty/whitespace-only strings
        ]
    session['chapters'] = chapter_strip_
    session['final_name'] = "test_audiobook_output"  # Ensure final_name is set to a valid string
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    # Call the function to test
    epub_processor = EPubProcessor()
    result = epub_processor.convert_chapters2audio(session_id, context)
    
    # Assert the result
    assert result == True, "Conversion of chapters to audio failed"
    
    # Check if audio files are created in chapters_dir
    audio_files = [f for f in os.listdir(test_session['chapters_dir']) if f.endswith('.flac')]
    assert len(audio_files) > 0, "No audio files were created in chapters directory"
    

def test_convert_chinese_chapter2audio(test_session):
    context, session_id, session = test_session
    # Read test file content
    test_file_path = "ebooks/god-1-2.txt"
    with open(test_file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split content into chapters for testing (assuming chapters are separated by some delimiter, here using empty line for simplicity)
    chapters = content.split("\n\n")
    chapter_strip_ = [
        re.split(r"[。，]", chapter)  # split on either 。 or ，
        for chapter in chapters
        if chapter.strip()  # filter out empty/whitespace-only strings
    ]
    test_session['chapters'] = chapter_strip_
    test_session['final_name'] = "test_audiobook_output"  # Ensure final_name is set to a valid string
    
    # Call the function to test
    epub_processor = EPubProcessor()
    result = epub_processor.convert_chapters2audio(session_id, context)
    
    # Assert the result
    assert result == True, "Conversion of chapters to audio failed"
    
    # Check if audio files are created in chapters_dir
    audio_files = [f for f in os.listdir(test_session['chapters_dir']) if f.endswith('.flac')]
    assert len(audio_files) > 0, "No audio files were created in chapters directory"
    

