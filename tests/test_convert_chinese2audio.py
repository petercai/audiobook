import os
import shutil
import pytest
from lib.functions import *
from lib.conf import *
from lib.models import *

from multiprocessing import Manager

@pytest.fixture
def test_session():
    # Initialize a session context for testing
    manager = Manager()
    session_id = "test_session"
    session = recursive_proxy(
        {
            "script_mode": "native",
            "id": session_id,
            "process_id": None,
            "device": "cpu",
            "system": None,
            "client": None,
            "language": "zho",
            "language_iso1": "zh-cn",
            "audiobook": None,
            "audiobooks_dir": os.path.join(tmp_dir, "test_audiobooks"),
            "process_dir": os.path.join(tmp_dir, "test_process"),
            "ebook": None,
            "ebook_list": None,
            "ebook_mode": "single",
            "chapters_dir": os.path.join(tmp_dir, "test_process", "chapters"),
            "chapters_dir_sentences": os.path.join(
                tmp_dir, "test_process", "chapters", "sentences"
            ),
            "epub_path": None,
            "filename_noext": None,
            "tts_engine": "xtts",
            "fine_tuned": "internal",
            "voice": None,
            "voice_dir": os.path.join(voices_dir, "__sessions", "test_voice"),
            "speaker_wav": os.path.join(
                voices_dir, "zho", "adult", "male", "yunjian_24000.wav"
            ),
            "custom_model": None,
            "custom_model_dir": os.path.join(models_dir, "__sessions", "test_model"),
            "toc": None,
            "chapters": None,
            "cover": None,
            "status": None,
            "progress": 0,
            "time": None,
            "cancellation_requested": False,
            "temperature": default_engine_settings[TTS_ENGINES["XTTSv2"]][
                "temperature"
            ],
            "length_penalty": default_engine_settings[TTS_ENGINES["XTTSv2"]][
                "length_penalty"
            ],
            "num_beams": default_engine_settings[TTS_ENGINES["XTTSv2"]]["num_beams"],
            "repetition_penalty": default_engine_settings[TTS_ENGINES["XTTSv2"]][
                "repetition_penalty"
            ],
            "top_k": default_engine_settings[TTS_ENGINES["XTTSv2"]]["top_k"],
            "top_p": default_engine_settings[TTS_ENGINES["XTTSv2"]]["top_p"],
            "speed": default_engine_settings[TTS_ENGINES["XTTSv2"]]["speed"],
            "enable_text_splitting": default_engine_settings[TTS_ENGINES["XTTSv2"]][
                "enable_text_splitting"
            ],
            "text_temp": default_engine_settings[TTS_ENGINES["BARK"]]["text_temp"],
            "waveform_temp": default_engine_settings[TTS_ENGINES["BARK"]][
                "waveform_temp"
            ],
            "event": None,
            "final_name": None,
            "output_format": "wav",
            "metadata": {
                "title": "Test Audiobook",
                "creator": "Test Author",
                "contributor": None,
                "language": "eng",
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
        },
        manager=manager,
    )
    
    # Create necessary directories
    os.makedirs(session['audiobooks_dir'], exist_ok=True)
    os.makedirs(session['process_dir'], exist_ok=True)
    os.makedirs(session['chapters_dir'], exist_ok=True)
    os.makedirs(session['chapters_dir_sentences'], exist_ok=True)
    os.makedirs(session['custom_model_dir'], exist_ok=True)
    os.makedirs(session['voice_dir'], exist_ok=True)
    
    return session

@pytest.fixture
def speaker_wav_yunjian():
     return os.path.join(
                voices_dir, "zho", "adult", "male", "yunjian_24000.wav"
            )

@pytest.fixture
def speaker_wav_yunxi():
   return os.path.join(
                voices_dir, "zho", "adult", "male", "yunxi_24000.wav"
            )

@pytest.fixture
def speaker_wav_yunyi():
       return os.path.join(
                voices_dir, "zho", "adult", "female", "yunyi_24000.wav"
            )


def test_convert_chinese2audio(test_session, speaker_wav_yunjian, speaker_wav_yunxi, speaker_wav_yunyi):
    test_session['speaker_wav'] = speaker_wav_yunjian

    # Read test file content
    test_file_path = "ebooks/god_one_sentense.txt"
    with open(test_file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split content into chapters for testing (assuming chapters are separated by some delimiter, here using empty line for simplicity)
    chapters = content.split('\n\n')
    chapter_strip_ = chapter_strip_ = [
            re.split(r'[。，]', chapter)   # split on either 。 or ，
            for chapter in chapters
            if chapter.strip()            # filter out empty/whitespace-only strings
        ]
    test_session['chapters'] = chapter_strip_
    test_session['final_name'] = "test_audiobook_output"  # Ensure final_name is set to a valid string
    
    # Call the function to test
    result = convert_chapters2audio(test_session)
    
    # Assert the result
    assert result == True, "Conversion of chapters to audio failed"
    
    # Check if audio files are created in chapters_dir
    audio_files = [f for f in os.listdir(test_session['chapters_dir']) if f.endswith('.flac')]
    assert len(audio_files) > 0, "No audio files were created in chapters directory"
    

def test_convert_chinese_chapter2audio(test_session, speaker_wav_yunjian, speaker_wav_yunxi, speaker_wav_yunyi):
    test_session['speaker_wav'] = speaker_wav_yunxi
    # Read test file content
    test_file_path = "ebooks/god-c1.txt"
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
    result = convert_chapters2audio(test_session)
    
    # Assert the result
    assert result == True, "Conversion of chapters to audio failed"
    
    # Check if audio files are created in chapters_dir
    audio_files = [f for f in os.listdir(test_session['chapters_dir']) if f.endswith('.flac')]
    assert len(audio_files) > 0, "No audio files were created in chapters directory"
    

if __name__ == "__main__":
    pytest.main(["-v", __file__])
