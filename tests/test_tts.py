import torch
from TTS.api import TTS
import pytest
import logging
logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def device():
  return "cuda" if torch.cuda.is_available() else "cpu"

@pytest.fixture(scope="module")
def tts(device):
  return TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

def test_list_models():
  models = TTS().list_models()
  for model in models:
    logger.info(model)
  assert isinstance(models, list)
  assert any("xtts_v2" in m for m in models)

def test_list_speakers(tts):
  speakers = tts.speakers
  for speaker in speakers:
    print(speaker)
  assert isinstance(speakers, list)
  assert len(speakers) > 0

def test_list_languages(tts):
  languages = tts.languages
  for lang in languages:
    print(lang)
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