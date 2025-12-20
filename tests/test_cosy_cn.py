import inspect
import os
import pytest
from ebooklib import epub

from lib import models
from lib.headless_processor import EBookProcessor
from lib.models import TTS_ENGINES, voices_dir
from lib.classes.tts_manager import TTSManager
from lib.mock_session import SessionContextMock, set_process_dir

tts_text = '二愣子睁大着双眼，直直望着茅草和烂泥糊成的黑屋顶，身上盖着的旧棉被，已呈深黄色，看不出原来的本来面目，还若有若无的散发着淡淡的霉味。'

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
            "ebook_list": None,
            "device": "cpu",
            "language": "zho",
            "language_iso1": "zh",
            "tts_engine": TTS_ENGINES['COSYVOICE'],
            "output_format": "m4b",
            "custom_model": None,
            "fine_tuned": "internal",
            "voice": None,
            "voice_dir": os.path.join(voices_dir, '__sessions', "test_voice"),
            # "speaker_wav": os.path.join(voices_dir, "zho", "adult", "male", "yunjian.wav"),
            # "temperature": 0.75,
            # "length_penalty": 1.0,
            # "num_beams": 5,
            # "repetition_penalty": 1.0,
            # "top_k": 50,
            # "top_p": 0.95,
            # "speed": 1.0,
            # "enable_text_splitting": True,
            # "text_temp": 0.7,
            # "waveform_temp": 0.7,
            "audiobooks_dir": tmp_path,
            "output_split": "by-chapter",
            "output_split_minutes": 30,
            "is_gui_process": False,
            "offline_mode": True,
            "script_mode": "native",
            "final_name": 'one-sentence.flac',

        }
    )
    session = context.get_session(session_id)
    return context, session_id, session



def test_cosyvoice_cn_zeroshot(session_context, ebook_path, tmp_path):
    context, session_id, session = session_context

    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    
    speaker = "default"  

    tts_manager = TTSManager(session)
    result = tts_manager.convert_sentence2audio(speaker, tts_text)
    # audio file in $process_dir/chapters/sentenses/{speaker}.flac
    assert result # Ture or False

    
def test_tts_en_ft_RosamundPike(session_context, ebook_path, tmp_path):
    context, session_id, session = session_context
    speaker = "RosamundPike"
    session.update({ "fine_tuned": speaker })
    # Create necessary directories
    process_dir = inspect.currentframe().f_code.co_name
    set_process_dir(session, process_dir)

    tts_manager = TTSManager(session)
    result = tts_manager.convert_sentence2audio(speaker, tts_text)
    # audio file in $process_dir/chapters/sentenses/{speaker}.flac
    assert result # Ture or False
    
def test_tts_en_ft_RafeBeckley(session_context, ebook_path, tmp_path):
    context, session_id, session = session_context
    speaker = "RafeBeckley"
    session.update({ "fine_tuned": speaker })
    # Create necessary directories
    process_dir = inspect.currentframe().f_code.co_name
    set_process_dir(session, process_dir)

    tts_manager = TTSManager(session)
    result = tts_manager.convert_sentence2audio(speaker, tts_text)
    # audio file in $process_dir/chapters/sentenses/{speaker}.flac
    assert result # Ture or False
    
def test_tts_en_ft_DermotCrowley(session_context, ebook_path, tmp_path):
    context, session_id, session = session_context
    speaker = "DermotCrowley"
    session.update({ "fine_tuned": speaker })
    # Create necessary directories
    process_dir = inspect.currentframe().f_code.co_name
    set_process_dir(session, process_dir)

    tts_manager = TTSManager(session)
    result = tts_manager.convert_sentence2audio(speaker, tts_text)
    # audio file in $process_dir/chapters/sentenses/{speaker}.flac
    assert result # Ture or False
    
def test_tts_en_ft_DavidAttenborough(session_context, ebook_path, tmp_path):
    context, session_id, session = session_context
    speaker = "DavidAttenborough"
    session.update({ "fine_tuned": speaker })
    # Create necessary directories
    process_dir = inspect.currentframe().f_code.co_name
    set_process_dir(session, process_dir)

    tts_manager = TTSManager(session)
    result = tts_manager.convert_sentence2audio(speaker, tts_text)
    # audio file in $process_dir/chapters/sentenses/{speaker}.flac
    assert result # Ture or False
    
def test_tts_en_ft_BryanCranston(session_context, ebook_path, tmp_path):
    context, session_id, session = session_context
    speaker = "BryanCranston"
    session.update({ "fine_tuned": speaker })
    # Create necessary directories
    process_dir = inspect.currentframe().f_code.co_name
    set_process_dir(session, process_dir)

    tts_manager = TTSManager(session)
    result = tts_manager.convert_sentence2audio(speaker, tts_text)
    # audio file in $process_dir/chapters/sentenses/{speaker}.flac
    assert result # Ture or False
