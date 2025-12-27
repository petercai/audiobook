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

from lib.text_normalizer import TextNormalizer
sys.stdout.reconfigure(encoding="utf-8")

@pytest.fixture
def tmp_path():
    return os.path.abspath('tmp')

@pytest.fixture
def ebook_path():
    return os.path.abspath('ebooks')

@pytest.fixture
def session_context(tmp_path: str):
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
        }
        }
    )
    session = context.get_session(session_id)


    return context, session_id, session

def test_convert2epub(session_context, ebook_path, tmp_path):
    """Test successful conversion of a .txt or .pdf file to .epub."""
    context, session_id, session = session_context
    # session = context.get_session(session_id)
    # Create necessary directories
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)

    input_file = os.path.join(ebook_path, "Dune.epub")

    session['ebook'] = str(input_file)
    session['epub_path'] = tmp_path+  "/book_gen.epub"

    processor = EPubProcessor()
    result = processor.convert2epub(session)

def test_process_epub_cn(session_context, ebook_path, tmp_path):
    """Test successful processing of an EPUB file."""
    context, session_id, session = session_context

    # Setup arguments for EBookProcessor
    args = {
        "ebook": os.path.join(ebook_path, "god-c12.epub"),
        "device": "cpu",
        "language": "zho",
        "language_iso1": "zh",
        "tts_engine": TTS_ENGINES['VOXCPM'],
        "voice_dir": os.path.join(voices_dir, '__sessions', "test_voice"),
        "speaker_wav": os.path.join(voices_dir, "zho", "adult", "male", "yunjian.wav"),
        # "enable_text_splitting": True,
        "output_format": "mb4",
    }
    # update session with args
    session.update(args)
    # Create necessary directories
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    session['epub_path'] = session['ebook']
    
    basename = os.path.basename(session["ebook"])
    name_splits = os.path.splitext(basename)
    session["filename_noext"] = name_splits[0]

    # Instantiate EBookProcessor
    from lib.headless_processor import EBookProcessor
    ebook_processor = EBookProcessor()
    # Process the EPUB
    status, success = ebook_processor.process_epub(session)

    # Assertions
    print(status)
    assert success
    assert "Audiobook(s)" in status
    assert os.path.exists(session['audiobook'])
    
def test_process_epub_en(session_context, ebook_path, tmp_path):
    """Test successful processing of an EPUB file."""
    context, session_id, session = session_context

    # Setup arguments for EBookProcessor
    args = {
        "ebook": os.path.join(ebook_path, "jane-eyre-c12.epub"),
        "device": "cpu",
        "language": "eng",
        "language_iso1": "en",
        "tts_engine": TTS_ENGINES['XTTSv2'],
        "output_format": "m4b",
        "offline_mode": True
    }
    # update session with args
    session.update(args)
    # Create necessary directories
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    session['epub_path'] = session['ebook']

    basename = os.path.basename(session["ebook"])
    name_splits = os.path.splitext(basename)
    session["filename_noext"] = name_splits[0]

    # Instantiate EBookProcessor
    from lib.headless_processor import EBookProcessor
    ebook_processor = EBookProcessor()
    # Process the EPUB
    status, success = ebook_processor.process_epub(session)

    # Assertions
    assert success is True
    assert "Audiobook(s)" in status
    assert os.path.exists(session['audiobook'])

def test_process_epub_en_mps(session_context, ebook_path, tmp_path):
    """Test successful processing of an EPUB file."""
    context, session_id, session = session_context

    # Setup arguments for EBookProcessor
    args = {
        "ebook": os.path.join(ebook_path, "jane-eyre-c12.epub"),
        "device": "mps",
        "language": "eng",
        "language_iso1": "en",
        "tts_engine": TTS_ENGINES['XTTSv2'],
        "output_format": "m4b",
        "offline_mode": True
    }
    # update session with args
    session.update(args)
    # Create necessary directories
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    session['epub_path'] = session['ebook']

    basename = os.path.basename(session["ebook"])
    name_splits = os.path.splitext(basename)
    session["filename_noext"] = name_splits[0]

    # Instantiate EBookProcessor
    from lib.headless_processor import EBookProcessor
    ebook_processor = EBookProcessor()
    # Process the EPUB
    status, success = ebook_processor.process_epub(session)

    # Assertions
    assert success is True
    assert "Audiobook(s)" in status
    assert os.path.exists(session['audiobook'])

def test_process_epub_chapters_cn(session_context, ebook_path, tmp_path):
    """Test successful processing of an EPUB file."""
    context, session_id, session = session_context

    # Setup arguments for EBookProcessor
    args = {
        "ebook": os.path.join(ebook_path, "god-c12.epub"),
        "ebook_list": None,
        "device": "cpu",
        "language": "zho",
        "language_iso1": "zh",
        "tts_engine": TTS_ENGINES['VOXCPM'],
        "output_format": "m4b",
    }
    # update session with args
    session.update(args)
    # Create necessary directories
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    session['epub_path'] = session['ebook']

    # Instantiate EBookProcessor
    from lib.headless_processor import EBookProcessor
    ebook_processor = EBookProcessor()
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

def test_process_epub_chapters_en(session_context, ebook_path, tmp_path):
    """Test successful processing of an EPUB file."""
    context, session_id, session = session_context
    # Setup arguments for EBookProcessor
    args = {
        "ebook": os.path.join(ebook_path, "jane-eyre-c12.epub"),
        "ebook_list": None,
        "device": "cpu",
        "language": "eng",
        "language_iso1": "en",
        "tts_engine": TTS_ENGINES['XTTSv2'],
        "output_format": "m4b",
    }
    # update session with args
    session.update(args)
    # Create necessary directories
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    session['epub_path'] = session['ebook']

    # Instantiate EBookProcessor
    from lib.headless_processor import EBookProcessor
    ebook_processor = EBookProcessor()
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

def test_process_epub_metadata_cn(session_context, ebook_path, tmp_path):
    context, session_id, session = session_context
    # Setup arguments for EBookProcessor
    args = {
        "session": session_id,
        'cancellation_requested': False,
        "ebook": os.path.join(ebook_path, "god-c12.epub"),
        "device": "cpu",
        "language": "zho",
        "language_iso1": 'zh',
        "tts_engine": TTS_ENGINES['VOXCPM'],
        "output_format": "m4b",
    }
    # update session with args
    session.update(args)
    # Create necessary directories
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    session['epub_path'] = session['ebook']

    # Instantiate EBookProcessor
    from lib.headless_processor import EBookProcessor
    ebook_processor = EBookProcessor()
    epubBook = epub.read_epub(session["epub_path"], {"ignore_ncx": True})
    basename = os.path.basename(session["ebook"])
    name_splits = os.path.splitext(basename)
    session["filename_noext"] = name_splits[0]

    # Process the EPUB
    status, success = ebook_processor.prepare_epub_metadata(session, epubBook)

    # Assertions
    assert success is True
    metadata = session['metadata']
    # print dict metadata
    for key, value in metadata.items():
        print(f"{key}: {value}")

def test_process_epub_metadata_en(session_context, ebook_path, tmp_path):
    context, session_id, session = session_context
    # Setup arguments for EBookProcessor
    args = {
        "session": session_id,
        'cancellation_requested': False,
        "ebook": os.path.join(ebook_path, "Dune.epub"),
        "device": "cpu",
        "language": "eng",
        "language_iso1": 'en',
        "tts_engine": TTS_ENGINES['XTTSv2'],
        "output_format": "m4b",
    }
    # update session with args
    session.update(args)
    # Create necessary directories
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    session['epub_path'] = session['ebook']

    # Instantiate EBookProcessor
    from lib.headless_processor import EBookProcessor
    ebook_processor = EBookProcessor()
    epubBook = epub.read_epub(session["epub_path"], {"ignore_ncx": True})
    basename = os.path.basename(session["ebook"])
    name_splits = os.path.splitext(basename)
    session["filename_noext"] = name_splits[0]

    # Process the EPUB
    status, success = ebook_processor.prepare_epub_metadata(session, epubBook)

    # Assertions
    assert success is True
    metadata = session['metadata']
    # print dict metadata
    for key, value in metadata.items():
        print(f"{key}: {value}")

def test_show_chapters_and_sentences_en(session_context, ebook_path, tmp_path):
    context, session_id, session = session_context
    # Setup arguments for EBookProcessor
    args = {
        "ebook": os.path.join(ebook_path, "jane-eyre-c12.epub"),
        "device": "cpu",
        "language": "eng",
        "language_iso1": 'en',
        "tts_engine": TTS_ENGINES['XTTSv2'],
    }

    # update session with args
    session.update(args)

    ebook_ = session["ebook"]
    epubBook = epub.read_epub(ebook_, {"ignore_ncx": True})

    processor = EPubProcessor()
    toc, chapters = processor.get_chapters_in_sentences(epubBook, session)
    # Assertions
    assert toc
    print(toc)
    assert chapters
    for chapter in chapters:
        for i, sentence in enumerate(chapter, 1):
            print(f"{i}: {sentence}")

def test_get_chapters_cn(session_context, ebook_path, tmp_path):
    context, session_id, session = session_context
    # Setup arguments for EBookProcessor
    args = {
        "ebook": os.path.join(ebook_path, "god-c12.epub"),
        "device": "cpu",
        "language": "zho",
        "language_iso1": 'zh',
        "tts_engine": TTS_ENGINES['VOXCPM'],
    }

    # update session with args
    session.update(args)

    ebook_ = session["ebook"]
    epubBook = epub.read_epub(ebook_, {"ignore_ncx": True})

    processor = EPubProcessor()
    toc, chapters = processor.get_chapters_in_sentences(epubBook, session)
    # Assertions
    assert toc
    print(toc)
    assert chapters
    for chapter in chapters:
        for i, sentence in enumerate(chapter, 1):
            print(f"{i}: {sentence}")

def test_get_epub_chapters_en(ebook_path: str):
    ebook_ = os.path.join(ebook_path, "jane-eyre-c12.epub")
    epubBook = epub.read_epub(ebook_, {"ignore_ncx": True})
    processor = EPubProcessor()
    docs, toc = processor.get_epub_chapters(epubBook, "eng")
    assert toc
    print(toc)
    assert docs
    # for chapter in chapters:
    #     for i, sentence in enumerate(chapter, 1):
    #         print(f"{i}: {sentence}")
def test_get_epub_chapters_cn(ebook_path: str):
    ebook_ = os.path.join(ebook_path, "god-c12.epub")
    epubBook = epub.read_epub(ebook_, {"ignore_ncx": True})
    processor = EPubProcessor()
    docs, toc = processor.get_epub_chapters(epubBook, "zho")
    assert toc
    print(toc)
    assert docs
    # for chapter in chapters:
    #     for i, sentence in enumerate(chapter, 1):
    #         print(f"{i}: {sentence}")

def test_get_cover(session_context, ebook_path, tmp_path):
    context, session_id, session = session_context
    # Setup arguments for EBookProcessor
    args = {
        "session": session_id,
        'cancellation_requested': False,
        "ebook": os.path.join(ebook_path, "思考,快与慢.epub"),
        "filename_noext": "思考-快与慢",
        "device": "cpu",
        "language": "zho",
        "language_iso1": 'zh',
        "tts_engine": TTS_ENGINES['XTTSv2'],
    }

    # update session with args
    session.update(args)
    # Create necessary directories
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    
    ebook_ = session["ebook"]
    epubBook = epub.read_epub(ebook_, {"ignore_ncx": True})

    processor = EPubProcessor()
    result = processor.get_cover(epubBook, session)
    # Assertions
    assert result
    print(result)


def test_get_chapter_sentences_4_dune(session_context, ebook_path: str, tmp_path: str):
    context, session_id, session = session_context
    args = {
        "session": session_id,
        'cancellation_requested': False,
        "ebook": os.path.join(ebook_path, "Dune.epub"),
        "device": "cpu",
        "language": "eng",
        "language_iso1": 'en',
        "tts_engine": TTS_ENGINES['XTTSv2'],

    }
    # update session with args
    session.update(args)
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    ebook_ = session["ebook"]
    epubBook = epub.read_epub(ebook_, {"ignore_ncx": True})

    processor = EPubProcessor()
    toc, chapters_with_tn_sentences = processor.get_chapters_in_sentences(epubBook, session)
    transcript_dir = os.path.join(session["process_dir"], "transcript")
    os.makedirs(transcript_dir, exist_ok=True)
    cache_transcript_by_chapter(chapters_with_tn_sentences, transcript_dir)
    created_files = sum(1 for entry in os.scandir(transcript_dir) if entry.is_file())
    assert created_files == len(chapters_with_tn_sentences)

def test_get_chapter_sentences_4_hunger_games(session_context, ebook_path: str, tmp_path: str):
    context, session_id, session = session_context
    args = {
        "session": session_id,
        'cancellation_requested': False,
        "ebook": os.path.join(ebook_path, "The Hunger Games-2008 - The Hunger Games (Suzanne Collins) .epub"),
        "device": "cpu",
        "language": "eng",
        "language_iso1": 'en',
        "tts_engine": TTS_ENGINES['XTTSv2'],

    }
    # update session with args
    session.update(args)
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    ebook_ = session["ebook"]
    epubBook = epub.read_epub(ebook_, {"ignore_ncx": True})

    processor = EPubProcessor()
    toc, chapters_with_tn_sentences = processor.get_chapters_in_sentences(epubBook, session)
    transcript_dir = os.path.join(session["process_dir"], "transcript")
    os.makedirs(transcript_dir, exist_ok=True)
    cache_transcript_by_chapter(chapters_with_tn_sentences, transcript_dir)
    created_files = sum(1 for entry in os.scandir(transcript_dir) if entry.is_file())
    assert created_files == len(chapters_with_tn_sentences)

def test_filter_chapter_cn(session_context, ebook_path: str, tmp_path: str):
    context, session_id, session = session_context
    args = {
        "session": session_id,
        'cancellation_requested': False,
        "ebook": os.path.join(ebook_path, "思考,快与慢.epub"),
        "device": "cpu",
        "language": "zho",
        "language_iso1": 'zh',
        "tts_engine": TTS_ENGINES['XTTSv2'],

    }

    # update session with args
    session.update(args)
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    
    ebook_ = session["ebook"]
    epubBook = epub.read_epub(ebook_, {"ignore_ncx": True})

    processor = EPubProcessor()
    epub_docs, toc = processor.get_epub_chapters(epubBook, session['language'])
    toc_epub_docs = processor.map_filter_chapters_to_toc(epub_docs, toc)
    transcript_dir = os.path.join(session["process_dir"], "transcript")
    chapters_with_tn_sentences = process_chapters(processor, toc_epub_docs, transcript_dir, session)
    cache_transcript_by_chapter(chapters_with_tn_sentences, transcript_dir)
    created_files = sum(1 for entry in os.scandir(transcript_dir) if entry.is_file())
    assert created_files == len(chapters_with_tn_sentences)

def test_filter_chapter_4_dune(session_context, ebook_path: str, tmp_path: str):
    context, session_id, session = session_context
    args = {
        "session": session_id,
        'cancellation_requested': False,
        "ebook": os.path.join(ebook_path, "Dune.epub"),
        "device": "cpu",
        "language": "eng",
        "language_iso1": 'en',
        "tts_engine": TTS_ENGINES['XTTSv2'],

    }
    # update session with args
    session.update(args)
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    
    ebook_ = session["ebook"]
    epubBook = epub.read_epub(ebook_, {"ignore_ncx": True})

    processor = EPubProcessor()
    epub_docs, toc = processor.get_epub_chapters(epubBook, session['language'])
    toc_epub_docs = processor.map_filter_chapters_to_toc(epub_docs, toc)
    transcript_dir = os.path.join(session["process_dir"], "transcript")
    chapters_with_tn_sentences = process_chapters(processor, toc_epub_docs, transcript_dir, session)
    cache_transcript_by_chapter(chapters_with_tn_sentences, transcript_dir)
    created_files = sum(1 for entry in os.scandir(transcript_dir) if entry.is_file())
    assert created_files == len(chapters_with_tn_sentences)
    
def test_filter_chapter_4_hunger_game(session_context, ebook_path: str, tmp_path: str):
    context, session_id, session = session_context
    args = {
        "session": session_id,
        'cancellation_requested': False,
        "ebook": os.path.join(ebook_path, "The Hunger Games-2008 - The Hunger Games (Suzanne Collins) .epub"),
        "device": "cpu",
        "language": "eng",
        "language_iso1": 'en',
        "tts_engine": TTS_ENGINES['XTTSv2'],

    }
    # update session with args
    session.update(args)
    func_name = inspect.currentframe().f_code.co_name
    set_process_dir(session, func_name)
    
    ebook_ = session["ebook"]
    epubBook = epub.read_epub(ebook_, {"ignore_ncx": True})

    processor = EPubProcessor()
    epub_docs, toc = processor.get_epub_chapters(epubBook, session['language'])
    toc_epub_docs = processor.map_filter_chapters_to_toc(epub_docs, toc)
    transcript_dir = os.path.join(session["process_dir"], "transcript")
    chapters_with_tn_sentences = process_chapters(processor, toc_epub_docs, transcript_dir, session)
    cache_transcript_by_chapter(chapters_with_tn_sentences, transcript_dir)
    created_files = sum(1 for entry in os.scandir(transcript_dir) if entry.is_file())
    assert created_files == len(chapters_with_tn_sentences)


def process_chapters(processor, toc_docs, transcript_dir, session):
    os.makedirs(transcript_dir, exist_ok=True)
    processed_chapters = []
    pending_sentences = []

    # language_ = session["language"]
    language_iso_ = session["language_iso1"]
    stanza_nlp = None
    if language_iso_ in year_to_decades_languages:
        try:
            # Download the required language model if not already present
            stanza.download(language_iso_, model_dir=os.path.join(models_dir, 'stanza'), logging_level='WARN',
                            verbose=False if session['offline_mode'] else None)
        except Exception as e:
            if session['offline_mode']:
                print(
                    f"Offline mode: Failed to find stanza model for '{language_iso_}'. Expected in '{os.path.join(models_dir, 'stanza')}'")
            raise e
        # Create a processing pipeline for tokenization and named entity recognition
        stanza_nlp = stanza.Pipeline(language_iso_, processors='tokenize,ner')

    processor.text_normalizer = TextNormalizer(language_iso_)
    for title, chapter_doc in toc_docs.items():
        chapter_sentences = processor.filter_chapter(
            chapter_doc,
            # lang=language_,
            lang_iso1=language_iso_,
            tts_engine=session["tts_engine"],
            stanza_nlp=stanza_nlp,
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

