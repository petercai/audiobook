import inspect
import os
import re
import pytest
from ebooklib import epub

from lib.models import TTS_ENGINES, voices_dir
from lib.classes.tts_manager import TTSManager
from lib.mock_session import SessionContextMock, set_process_dir

tts_text = '二愣子睁大着双眼，直直望着茅草和烂泥糊成的黑屋顶，身上盖着的旧棉被，已呈深黄色，看不出原来的本来面目，还若有若无的散发着淡淡的霉味。'
tts_text = '自从读过克莱因于20世纪70年代撰写的一篇论文的草稿之后，我曾一度非常推崇他关于消防员专业技能的研究，他的著作《力量的源泉》也给我留下了深刻的印象.'
tts_text_en = 'Maintaining your ability to learn translates into increased marketability, improved career optionsand higher salaries.'

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
            "voice": os.path.join(voices_dir, "zho", "adult", "male", "yunyang.wav"),
            # "voice_dir": os.path.join(voices_dir, '__sessions', "test_voice"),
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


def pick_speaker(session, category, voice_file):
    voice_path = os.path.join(voices_dir, "zho", "adult", category, voice_file)
    session["voice"] = voice_path
    return re.sub(r'\.wav$', '', os.path.basename(voice_path))



def test_cosyvoice_cn_zeroshot_yunyang(session_context):
    context, session_id, session = session_context
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    speaker = pick_speaker(session, "male", "yunyang.wav")

    tts_manager = TTSManager(session)
    result = tts_manager.convert_sentence2audio(speaker, tts_text)
    # audio file in $process_dir/chapters/sentenses/{speaker}.flac
    assert result

def test_cosyvoice_cn_zeroshot_yunxi(session_context):
    context, session_id, session = session_context
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    speaker = pick_speaker(session, "male", "yunxi.wav")

    tts_manager = TTSManager(session)
    result = tts_manager.convert_sentence2audio(speaker, tts_text)
    # audio file in $process_dir/chapters/sentenses/{speaker}.flac
    assert result
    
def test_cosyvoice_cn_zeroshot_yunjian(session_context):
    context, session_id, session = session_context
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    speaker = pick_speaker(session, "male", "yunjian.wav")

    tts_manager = TTSManager(session)
    result = tts_manager.convert_sentence2audio(speaker, tts_text)
    # audio file in $process_dir/chapters/sentenses/{speaker}.flac
    assert result
def test_cosyvoice_cn_zeroshot_yunxia(session_context):
    context, session_id, session = session_context
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    speaker = pick_speaker(session, "female", "yunxia.wav")

    tts_manager = TTSManager(session)
    result = tts_manager.convert_sentence2audio(speaker, tts_text)
    # audio file in $process_dir/chapters/sentenses/{speaker}.flac
    assert result
def test_cosyvoice_cn_zeroshot_yunxiao(session_context):
    context, session_id, session = session_context
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    speaker = pick_speaker(session, "female", "yunxiao.wav")

    tts_manager = TTSManager(session)
    result = tts_manager.convert_sentence2audio(speaker, tts_text)
    # audio file in $process_dir/chapters/sentenses/{speaker}.flac
    assert result
def test_cosyvoice_cn_zeroshot_yunyi(session_context):
    context, session_id, session = session_context
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    speaker = pick_speaker(session, "female", "yunyi.wav")

    tts_manager = TTSManager(session)
    result = tts_manager.convert_sentence2audio(speaker, tts_text)
    # audio file in $process_dir/chapters/sentenses/{speaker}.flac
    assert result
    
def test_cosyvoice_cn_ft_male(session_context):
    context, session_id, session = session_context
    
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    session["voice"] = None
    session['fine_tuned'] = "ChineseMale"
    tts_manager = TTSManager(session)
    result = tts_manager.convert_sentence2audio(session['fine_tuned'], tts_text)
    # audio file in $process_dir/chapters/sentenses/{speaker}.flac
    assert result
def test_cosyvoice_cn_ft_female(session_context):
    context, session_id, session = session_context
    
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    session["voice"] = None
    session['fine_tuned'] = "ChineseFemale"
    tts_manager = TTSManager(session)
    result = tts_manager.convert_sentence2audio(session['fine_tuned'], tts_text)
    # audio file in $process_dir/chapters/sentenses/{speaker}.flac
    assert result
def test_cosyvoice_cn_ft_cantonese(session_context):
    context, session_id, session = session_context
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    session["voice"] = None
    session['fine_tuned'] = "CantoneseFemale"
    tts_manager = TTSManager(session)
    result = tts_manager.convert_sentence2audio(session['fine_tuned'], tts_text)
    # audio file in $process_dir/chapters/sentenses/{speaker}.flac
    assert result


def test_cosyvoice_en_ft_male(session_context):
    context, session_id, session = session_context
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    session["device"] = "cpu"
    session["language"] = "eng"
    session["language_iso1"] = "en"
    session["voice"] = None
    session['fine_tuned'] = "EnglishMale"
    tts_manager = TTSManager(session)
    result = tts_manager.convert_sentence2audio(session['fine_tuned'], tts_text_en)
    # audio file in $process_dir/chapters/sentenses/{speaker}.flac
    assert result
def test_cosyvoice_en_ft_female(session_context):
    context, session_id, session = session_context
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    session["device"] = "mps"
    session["language"] = "eng"
    session["language_iso1"] = "en"
    session["voice"] = None
    session['fine_tuned'] = "EnglishFemale"
    tts_manager = TTSManager(session)
    result = tts_manager.convert_sentence2audio(session['fine_tuned'], tts_text_en)
    # audio file in $process_dir/chapters/sentenses/{speaker}.flac
    assert result
