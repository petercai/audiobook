
import inspect
import os
import pytest
from ebooklib import epub

from lib.models import TTS_ENGINES
from lib.conf import voices_dir
from lib.epub import EPubProcessor
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
    toc, chapters = processor.get_chapters_in_sentences(epubBook, session, 7)
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

def test_get_epub_chapters_en(ebook_path):
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
def test_get_epub_chapters_cn(ebook_path):
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


def test_filter_chapter(session_context, ebook_path, tmp_path):
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
    all_docs, toc = processor.get_epub_chapters(epubBook, session['language'])
    
    doc_by_name = {}
    doc_by_basename = {}
    for doc in all_docs:
        doc_name = getattr(doc, "file_name", None) or getattr(doc, "href", None)
        if doc_name:
            doc_by_name[doc_name] = doc
            doc_by_basename[os.path.basename(doc_name)] = doc

    def iter_toc_items(items):
        for item in items:
            if isinstance(item, (list, tuple)) and len(item) == 2 and isinstance(item[1], (list, tuple)):
                section, children = item
                yield section
                if children:
                    yield from iter_toc_items(children)
            else:
                yield item

    toc_docs = {}
    for item in iter_toc_items(toc):
        title = getattr(item, "title", None)
        href = getattr(item, "href", None) or getattr(item, "file_name", None)
        if not (title and href):
            continue
        href_base = href.split("#", 1)[0]
        doc = doc_by_name.get(href) or doc_by_name.get(href_base) or doc_by_basename.get(os.path.basename(href_base))
        if doc is not None:
            toc_docs[title] = doc
    
    transcript_dir = os.path.join(session["process_dir"], "transcript")
    os.makedirs(transcript_dir, exist_ok=True)
    toc_count = len(toc_docs)
    number_width = max(1, len(str(toc_count)))
    for chapter_index, chapter_doc in enumerate(toc_docs.values(), 1):
        chapter_sentences = processor.filter_chapter(
            chapter_doc,
            lang='zho',
            lang_iso1='zh',
            tts_engine='xtts',
            stanza_nlp=True,
            is_num2words_compat=True
        )
        chapter_filename = f"c{chapter_index:0{number_width}d}.txt"
        chapter_path = os.path.join(transcript_dir, chapter_filename)
        with open(chapter_path, "w", encoding="utf-8") as chapter_file:
            chapter_file.write("\n".join(chapter_sentences))

    created_files = sum(1 for entry in os.scandir(transcript_dir) if entry.is_file())
    assert created_files == toc_count

