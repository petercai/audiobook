from math import log
import torch
from TTS.api import TTS
import pytest
import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# File handler
file_handler = logging.FileHandler("test_tts.log")
file_handler.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

# Add handlers to logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)


@pytest.fixture(scope="module")
def device():
  return "cuda" if torch.cuda.is_available() else "cpu"

@pytest.fixture(scope="module")
def tts(device):
  _tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
  return _tts

def test_list_models():
  models = TTS().list_models()
  logger.info("models")
  for model in models:
    logger.info(model)
  assert isinstance(models, list)
  assert any("xtts_v2" in m for m in models)

def test_list_speakers(tts):
  speakers = tts.speakers
  logger.info("speakers of model " + tts.model_name)
  for speaker in speakers:
    logger.info(speaker)
  assert isinstance(speakers, list)
  assert len(speakers) > 0

def test_list_languages(tts):
  languages = tts.languages
  logger.info("languages of model " + tts.model_name)
  for lang in languages:
    logger.info(lang)
  assert isinstance(languages, list)
  assert "en" in languages

def test_tts_to_file(tts, tmp_path):
  text = "The big ball of yellow might be spilling into the clouds, runny and yolky and blurring into the bluest sky, bright with cold hope and false promises about fond memories, real families, hearty breakfasts, stacks of pancakes drizzled in maple syrup sitting on a plate in a world that doesn’t exist anymore."
  speaker_wav = "voices/eng/adult/female/AlexandraHisakawa.wav"
  file_path = tmp_path / "Alexandra.wav"
  tts.tts_to_file(
    text=text,
    speaker_wav=speaker_wav,
    language="en",
    file_path=str(file_path),
    split_sentences=True
  )
  assert file_path.exists()
  assert file_path.stat().st_size > 0

def test_tts_eng(tts):
  # TTS to a file, use a preset speaker
  tts.tts_to_file(
    text="The big ball of yellow might be spilling into the clouds, runny and yolky and blurring into the bluest sky, bright with cold hope and false promises about fond memories, real families, hearty breakfasts, stacks of pancakes drizzled in maple syrup sitting on a plate in a world that doesn’t exist anymore.",
    # speaker="Craig Gutsy",
    speaker_wav="voices/eng/adult/female/AlexandraHisakawa.wav",
    language="en",
    file_path="Alexandra.wav",
    split_sentences=True
  )