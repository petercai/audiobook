from lib.functions import convert_ebook


class TestConvertBook:
    args = {
        "audiobooks_dir": "C:workspacegithubaudiobookebook2audiobookaudiobookscli",
        "custom_model": None,
        "device": "cpu",
        "ebook": "C:workspacegithubaudiobookebook2audiobookebooksUnravelMe.epub",
        "ebook_list": None,
        "ebooks_dir": None,
        "enable_text_splitting": False,
        "fine_tuned": "internal",
        "headless": True,
        "is_gui_process": False,
        "language": "eng",
        "language_iso1": "en",
        "length_penalty": None,
        "num_beams": None,
        "output_dir": None,
        "output_format": "m4b",
        "repetition_penalty": None,
        "script_mode": "native",
        "session": None,
        "share": False,
        "speed": None,
        "temperature": None,
        "text_temp": None,
        "top_k": None,
        "top_p": None,
        "tts_engine": None,
        "voice": None,
        "waveform_temp": None,
        "workflow": False
    }
    def test_convert_book(self):
        convert_ebook(self.args)