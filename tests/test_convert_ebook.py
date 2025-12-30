import inspect
import os
import pytest

from lib.functions import models_dir, voices_dir
from lib.headless_processor import EBookProcessor
from lib.mock_session import SessionContextMock, set_process_dir
from lib.conf import audiobooks_cli_dir, default_output_format, default_output_split, default_output_split_minutes
from lib.models import TTS_ENGINES, default_engine_settings

@pytest.fixture
def ebook_path():
    return os.path.abspath('ebooks')

@pytest.fixture
def context():
    # Initialize a session context for testing
    session_id = "test-session"
    context = SessionContextMock(
        {
        "script_mode": "native",
        "session": session_id,
        "process_id": None,
        "device": 'cpu',
        "system": None,
        "client": None,
        "language": 'eng',
        "language_iso1": "en",
        "audiobook": None,
        "audiobooks_dir": audiobooks_cli_dir,
        "ebook": None,
        "ebook_list": None,
        "ebook_mode": "single",
        "epub_path": None,
        "filename_noext": None,
        "tts_engine": 'xtts',
        "fine_tuned": 'internal',
        "voice": None,
        "voice_dir": os.path.join(voices_dir, '__sessions', "test_voice"),
        "custom_model": None,
        "custom_model_dir": os.path.join(models_dir, '__sessions', "test_model"),
        "toc": None,
        "chapters": None,
        "cover": None,
        "status": None,
        "progress": 0,
        "time": None,
        "cancellation_requested": False,
        "event": None,
        "final_name": None,
        "output_format": 'wav',
        "offline_mode": False,
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
        },
    })

    return context

@pytest.fixture
def args():
    args = {
        "script_mode": "native",
        "is_gui_process": False,
        "session": "test-session",
        "process_id": None,
        "device": 'cpu',
        "system": None,
        "client": None,
        "language": 'eng',
        "language_iso1": "en",
        "audiobook": None,
        "audiobooks_dir": audiobooks_cli_dir,
        "ebook": None,
        "ebook_list": None,
        "ebook_mode": "single",
        "epub_path": None,
        "filename_noext": None,
        "tts_engine": 'xtts',
        "fine_tuned": 'internal',
        "voice": None,
        "voice_dir": os.path.join(voices_dir, '__sessions', "test_voice"),
        "custom_model": None,
        "custom_model_dir": os.path.join(models_dir, '__sessions', "test_model"),
        "toc": None,
        "chapters": None,
        "cover": None,
        "status": None,
        "progress": 0,
        "time": None,
        "cancellation_requested": False,
        "event": None,
        "final_name": None,
        "output_format": 'wav',
        "offline_mode": False,
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
        },
        "temperature": default_engine_settings['xtts']['temperature'],
        "length_penalty": default_engine_settings['xtts']['length_penalty'],
        "num_beams": default_engine_settings['xtts']['num_beams'],
        "repetition_penalty": default_engine_settings['xtts']['repetition_penalty'],
        "top_k": default_engine_settings['xtts']['top_k'],
        "top_p": default_engine_settings['xtts']['top_p'],
        "speed": default_engine_settings['xtts']['speed'],
        "enable_text_splitting": default_engine_settings['xtts']['enable_text_splitting'],
        "text_temp": default_engine_settings['bark']['text_temp'],
        "waveform_temp": default_engine_settings['bark']['waveform_temp'],        
        
    } 
    return args

def test_convert_en_ebook(args, context, ebook_path):
    book_filename = "UnravelMe-c12.epub"
    book_name = book_filename.split(".")[0]  
    args = { **args,
        "session": book_name,
        "id": book_name,
        "ebook": os.path.join(ebook_path, book_filename),
        "device": "cpu",
        "add_toc_title": True,
        "language_iso1": "en",
        "tts_engine": TTS_ENGINES["XTTSv2"],
        "output_format": default_output_format,
        "output_split": default_output_split,
        "output_split_minutes": default_output_split_minutes,
        'final_name':  book_name  # Ensure final_name is set to a valid string
    }    
    context.set_session(args)
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(args, func_name)
    
    # Call the function to test
    processor = EBookProcessor()
    status, result = processor.convert_ebook(args, context)
    assert result
    

def test_convert_cn_ebook(args, context, ebook_path):
    book_filename = "god-c12.epub"
    book_name = book_filename.split(".")[0]  
    args = {
        "session": book_name,
        "ebook": os.path.join(ebook_path, book_filename),
        "device": "cpu",
        "add_toc_title": True,
        "language_iso1": "zh",
        "tts_engine": TTS_ENGINES["COSYVOICE"],
        'final_name':  book_name  # Ensure final_name is set to a valid string
    }    
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(args, func_name)
    
    # Call the function to test
    processor = EBookProcessor()
    status, result = processor.convert_ebook(args, context)
    assert result
    