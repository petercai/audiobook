import inspect
import os

import pytest
from ebooklib import epub
import stanza
from lib.lang import year_to_decades_languages
from lib.models import TTS_ENGINES
from lib.conf import voices_dir, models_dir
from lib.epub import EPubProcessor
from lib.mock_session import SessionContextMock, set_process_dir

import sys

from syntrive.adapters.text.normalizer import TextNormalizer

sys.stdout.reconfigure(encoding="utf-8")


@pytest.fixture
def tmp_path():
    return os.path.abspath("tmp")


@pytest.fixture
def ebook_path():
    return os.path.abspath("ebooks")


@pytest.fixture
def session_context(tmp_path: str):
    """Fixture to create a temporary session context for tests."""
    session_id = "test-session"
    context = SessionContextMock(
        {
            "session": session_id,
            "cancellation_requested": False,
            # "ebook": os.path.join(ebook_path, "jane-eyre-c12.epub"),
            # "chapters_dir": os.path.join(process_dir, "chapters"),
            # "chapters_dir_sentences": os.path.join(process_dir, "chapters", "sentences"),
            "ebook_list": None,
            "device": "cpu",
            "language_iso1": "en",
            "tts_engine": TTS_ENGINES["XTTSv2"],
            "output_format": "m4b",
            "custom_model": None,
            "fine_tuned": "internal",
            "voice": None,
            "voice_dir": os.path.join(voices_dir, "__sessions", "test_voice"),
            "speaker_wav": os.path.join(
                voices_dir, "zho", "adult", "male", "yunjian.wav"
            ),
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
            "output_split": "by-chapter",
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
            },
        }
    )
    session = context.get_session(session_id)
    return context, session_id, session


def test_get_chapter_sentences_jan_eyre(session_context, ebook_path: str, tmp_path: str):
    context, session_id, session = session_context
    args = {
        "session": session_id,
        "cancellation_requested": False,
        "ebook": os.path.join(ebook_path, "charlotte-bronte_jane-eyre.epub"),
        "device": "cpu",
        "add_toc_title": True,
        "language_iso1": "en",
        "tts_engine": TTS_ENGINES["XTTSv2"],
    }
    # update session with args
    session.update(args)
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    ebook_ = session["ebook"]
    epubBook = epub.read_epub(ebook_, {"ignore_ncx": True})
    processor = EPubProcessor(session)
    toc, chapters_with_tn_sentences = processor.get_chapters_in_sentences(
        epubBook, session
    )
    transcript_dir = os.path.join(session["process_dir"], "chapters")
    os.makedirs(transcript_dir, exist_ok=True)
    cache_transcript_by_chapter(chapters_with_tn_sentences, transcript_dir)
    created_files = sum(1 for entry in os.scandir(transcript_dir) if entry.is_file())
    print(f"created_files: {created_files}")

def test_get_chapter_sentences_4_dune(session_context, ebook_path: str, tmp_path: str):
    context, session_id, session = session_context
    args = {
        "session": session_id,
        "cancellation_requested": False,
        "ebook": os.path.join(ebook_path, "Dune.epub"),
        "device": "cpu",
        "add_toc_title": True,
        "language_iso1": "en",
        "tts_engine": TTS_ENGINES["XTTSv2"],
    }
    # update session with args
    session.update(args)
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    ebook_ = session["ebook"]
    epubBook = epub.read_epub(ebook_, {"ignore_ncx": True})
    processor = EPubProcessor(session)
    toc, chapters_with_tn_sentences = processor.get_chapters_in_sentences(
        epubBook, session
    )
    transcript_dir = os.path.join(session["process_dir"], "chapters")
    os.makedirs(transcript_dir, exist_ok=True)
    cache_transcript_by_chapter(chapters_with_tn_sentences, transcript_dir)
    created_files = sum(1 for entry in os.scandir(transcript_dir) if entry.is_file())
    assert created_files == 48
    assert created_files == len(chapters_with_tn_sentences)

def test_get_chapter_sentences__Grea_Power_Politics(session_context, ebook_path: str, tmp_path: str):
    context, session_id, session = session_context
    args = {
        "session": session_id,
        "cancellation_requested": False,
        "ebook": os.path.join(ebook_path, "The Tragedy of Great Power Politics.epub"),
        "device": "cpu",
        "add_toc_title": False,
        "language_iso1": "en",
        "tts_engine": TTS_ENGINES["XTTSv2"],
    }
    # update session with args
    session.update(args)
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    ebook_ = session["ebook"]
    epubBook = epub.read_epub(ebook_, {"ignore_ncx": True})
    processor = EPubProcessor(session)
    toc, chapters_with_tn_sentences = processor.get_chapters_in_sentences(
        epubBook, session
    )
    transcript_dir = os.path.join(session["process_dir"], "chapters")
    os.makedirs(transcript_dir, exist_ok=True)
    cache_transcript_by_chapter(chapters_with_tn_sentences, transcript_dir)
    created_files = sum(1 for entry in os.scandir(transcript_dir) if entry.is_file())
    assert created_files == 11
    assert created_files == len(chapters_with_tn_sentences)


def test_get_chapter_sentences_4_hunger_games(
    session_context, ebook_path: str, tmp_path: str
):
    context, session_id, session = session_context
    args = {
        "session": session_id,
        "cancellation_requested": False,
        "ebook": os.path.join(
            ebook_path,
            "The Hunger Games-2008 - The Hunger Games (Suzanne Collins) .epub",
        ),
        "device": "cpu",
        "add_toc_title": True,
        "language_iso1": "en",
        "tts_engine": TTS_ENGINES["XTTSv2"],
    }
    # update session with args
    session.update(args)
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    ebook_ = session["ebook"]
    epubBook = epub.read_epub(ebook_, {"ignore_ncx": True})
    processor = EPubProcessor(session)
    toc, chapters_with_tn_sentences = processor.get_chapters_in_sentences(
        epubBook, session
    )
    transcript_dir = os.path.join(session["process_dir"], "chapters")
    os.makedirs(transcript_dir, exist_ok=True)
    cache_transcript_by_chapter(chapters_with_tn_sentences, transcript_dir)
    created_files = sum(1 for entry in os.scandir(transcript_dir) if entry.is_file())
    assert created_files == 27
    assert created_files == len(chapters_with_tn_sentences)


def process_filter_chapter(session):
    ebook_ = session["ebook"]
    epubBook = epub.read_epub(ebook_, {"ignore_ncx": True})
    processor = EPubProcessor(session)
    processor.text_normalizer = TextNormalizer(session["language_iso1"])
    epub_docs, toc = processor.get_epub_chapters(epubBook)
    toc_items = list(processor.toc_items_iter(toc))
    toc_epub_docs = processor.filter_chapters_with_toc(epub_docs, toc)
    transcript_dir = os.path.join(session["process_dir"], "chapters")
    chapters_with_tn_sentences = process_chapters(
        processor, toc_epub_docs, transcript_dir, session
    )
    cache_transcript_by_chapter(chapters_with_tn_sentences, transcript_dir)
    created_files = sum(1 for entry in os.scandir(transcript_dir) if entry.is_file())
    return chapters_with_tn_sentences, created_files


def process_chapters(processor, toc_docs, transcript_dir, session):
    os.makedirs(transcript_dir, exist_ok=True)
    processed_chapters = []
    pending_sentences = []

    # language_ = session["language"]
    language_iso_ = session["language_iso1"]


    processor.text_normalizer = TextNormalizer(language_iso_, session["offline_mode"])
    for chapter_doc, title in toc_docs.items():
        chapter_sentences = processor.filter_chapter(
            chapter_doc,
            tts_engine=session["tts_engine"],
        )
        if not chapter_sentences:
            continue
        if len(chapter_sentences) < 3:
            pending_sentences.extend(chapter_sentences)
            continue
        chapter_sentences = [title] + chapter_sentences
        if pending_sentences:
            chapter_sentences = pending_sentences + chapter_sentences
            pending_sentences = []
        processed_chapters.append(chapter_sentences)

    if pending_sentences:
        if processed_chapters:
            processed_chapters[-1].extend(pending_sentences)
        else:
            processed_chapters.append(pending_sentences)

    return processed_chapters
    # return cache_transcript_by_chapter(processed_chapters, transcript_dir)


def cache_transcript_by_chapter(chapters, transcript_dir):
    chapter_count = len(chapters)
    number_width = max(1, len(str(chapter_count)))
    for chapter_index, chapter_sentences in enumerate(chapters, 1):
        chapter_filename = f"c{chapter_index:0{number_width}d}.txt"
        chapter_path = os.path.join(transcript_dir, chapter_filename)
        with open(chapter_path, "w", encoding="utf-8") as chapter_file:
            chapter_file.write("\n".join(chapter_sentences))
    return chapter_count
