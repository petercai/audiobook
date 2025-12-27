import regex as re

import pytest
import stanza

from lib.lang import default_language_code
from lib.models import TTS_SML
from lib.text_normalizer import TextNormalizer


@pytest.fixture
def tn():
    TextNormalizer._resolve_lang_codes.cache_clear()
    return TextNormalizer("en")


@pytest.fixture
def tn_no_num2words():
    TextNormalizer._resolve_lang_codes.cache_clear()
    return TextNormalizer("zzz")


@pytest.fixture(scope="session")
def stanza_nlp():
    return stanza.Pipeline("en", processors="tokenize,ner", logging_level="ERROR")


def test_init_sets_sml_tokens(tn):
    assert TTS_SML["break"] in tn.sml_tokens
    assert TTS_SML["pause"] in tn.sml_tokens


def test_resolve_lang_codes_variants():
    TextNormalizer._resolve_lang_codes.cache_clear()
    iso1, iso3 = TextNormalizer._resolve_lang_codes("en")
    assert iso1 == "en"
    assert iso3

    iso1, iso3 = TextNormalizer._resolve_lang_codes("eng")
    assert iso3

    iso1, iso3 = TextNormalizer._resolve_lang_codes("zh-CN")
    assert iso1 == "zh"
    assert iso3

    iso1, iso3 = TextNormalizer._resolve_lang_codes("zzz")
    assert iso3 == "zzz" or iso3 == default_language_code


def test_num2words_lang():
    assert TextNormalizer._num2words_lang(None) == "en"
    assert TextNormalizer._num2words_lang("zh") == "zh_CN"
    assert TextNormalizer._num2words_lang("en") == "en"


def test_get_max_chars():
    assert TextNormalizer.get_max_chars("en") > 0


def test_get_num2words_compat_returns_bool():
    assert isinstance(TextNormalizer("en").is_num2words_compat, bool)


def test_normalize_text_4_tts_english(tn):
    text = "Chapter IV. Meet at 01:15. 2+3=5."
    out = tn.normalize_text_4_tts(text, "en", tts_engine=None, stanza_nlp=None)
    assert isinstance(out, list)
    assert out


def test_normalize_text_4_tts_chinese():
    text = "第IV章 12:30"
    tn = TextNormalizer("zho")
    out = tn.normalize_text_4_tts(text, "zho", tts_engine=None, stanza_nlp=None)
    assert isinstance(out, list)
    print(','.join(out))
    assert out


def test_num_repl_year_and_number(tn):
    match_year = re.match(r"(\d+)", "2024")
    assert tn._num_repl(match_year, "en") == "2024"

    match_num = re.match(r"(\d+)", "12")
    out = tn._num_repl(match_num, "en")
    assert isinstance(out, str)


def test_num2date_with_nlp_spans(tn, stanza_nlp):
    text = "On 1st 2024, 3."
    out = tn._num2dateWithNLP(text, stanza_nlp, "en", tts_engine=None)
    assert isinstance(out, str)
    assert out


def test_num2date_with_nlp_no_spans(tn_no_num2words, stanza_nlp):
    text = "Today is 1st 2024"
    out = tn_no_num2words._num2dateWithNLP(text, stanza_nlp, "en", tts_engine=None)
    assert isinstance(out, str)


def test_num2date_with_nlp_no_numbers(tn):
    text = "No numbers here"
    out = tn._num2dateWithNLP(text, stanza_nlp=None, lang_iso1="en", tts_engine=None)
    assert out == text


def test_split_inclusive(tn):
    pattern = re.compile(r"(.*?\.)")
    out = tn._split_inclusive("A. B. C", pattern)
    assert out == ["A.", "B.", "C"]


def test_segment_ideogramms_zho_real(tn):
    import jieba
    out = tn._segment_ideogramms(f"你好{TTS_SML['break']}世界", "zho")
    assert TTS_SML["break"] in out
    print(out)
    assert any(token.strip() for token in out)


def test_segment_ideogramms_jpn_real(tn):
    import sudachipy
    out = tn._segment_ideogramms("日本語", "jpn")
    assert isinstance(out, list)
    assert out


def test_segment_ideogramms_thai_real(tn):
    import pythainlp
    out = tn._segment_ideogramms("สวัสดี", "tha")
    assert isinstance(out, list)
    assert out


def test_segment_ideogramms_default_language(tn):
    out = tn._segment_ideogramms("abc", "en")
    assert out == ["abc"]


def test_join_ideogramms(tn):
    tokens = ["ab", "cd", TTS_SML["break"], "ef"]
    out = list(tn._join_ideogramms(tokens, max_chars=3))
    assert out == ["ab", "cd", TTS_SML["break"], "ef"]


def test_repl_abbreviations(tn):
    mapping = {"Dr.": "Doctor"}
    match = re.match(r"(Dr\.)", "Dr.")
    assert tn._repl_abbreviations(match, mapping) == "Doctor"


def test_n2w_paths(tn, tn_no_num2words):
    assert isinstance(tn._n2w(5, "en", None), str)
    assert isinstance(tn_no_num2words._n2w(5, "en", None), str)


def test_repl_clock_num_invalid_time(tn):
    m = re.match(r"(\d{1,2})[:.](\d{1,2})(?:[:.](\d{1,2}))?", "25:00")
    assert tn._repl_clock_num(m, "en", None) == "25:00"


def test_repl_clock_num_branches(tn):
    def repl(text):
        m = re.match(r"(\d{1,2})[:.](\d{1,2})(?:[:.](\d{1,2}))?", text)
        return tn._repl_clock_num(m, "en", None)

    assert repl("00:00") == "midnight"
    assert "quarter" in repl("01:15")
    assert "half" in repl("01:30")
    assert "quarter" in repl("01:45")
    assert "past" in repl("01:10")
    assert "to" in repl("01:50")
    assert "seconds" in repl("01:10:05")


def test_normalize_commas(tn):
    assert tn._normalize_commas("1,234,567") == "1,234,567"
    assert tn._normalize_commas("1234.50") == "1,234.50"


def test_clean_single_num(tn):
    assert tn._clean_single_num("inf", "en") == "inf"
    assert tn._clean_single_num("nan", "en") == "nan"
    assert tn._clean_single_num("not-a-number", "en") == "not-a-number"
    assert tn._clean_single_num("1e9999", "en") == "1e9999"
    assert isinstance(tn._clean_single_num("1234", "en"), str)


def test_clean_formatted_number_match(tn):
    number_re = re.compile(
        r"(?<!\w)"
        r"(\d{1,18}(?:,\s*\d{1,18})*(?:\.\d{1,12})?)"
        r"(?:\s*([---])\s*"
        r"(\d{1,18}(?:,\s*\d{1,18})*(?:\.\d{1,12})?))?"
        r"([^\w\s]*)",
        re.UNICODE,
    )
    m = number_re.match("12-34")
    out = tn._clean_formatted_number_match(m, "en")
    assert "-" in out


def test_repl_ambiguous(tn):
    ambiguous = {"-": "minus", "/": "over", "x": "times", "*": "times"}
    pattern = re.compile(r"(?<!\S)(\d+)\s*([-/*x])\s*(\d+)(?!\S)|(?<!\S)([-/*x])\s*(\d+)(?!\S)")
    m = pattern.match("2-3")
    assert tn._repl_ambiguous(m, ambiguous) == "2 minus 3"


def test_ordinal_to_words(tn, tn_no_num2words):
    m = re.match(r"(\d+)", "1")
    out = tn._TextNormalizer__ordinal_to_words(m, "en")
    assert isinstance(out, str)
    out = tn_no_num2words._TextNormalizer__ordinal_to_words(m, "en")
    assert out == "1"


def test_roman_helpers(tn):
    assert tn._is_valid_roman("IV")
    assert not tn._is_valid_roman("IIII")
    assert tn._roman_to_int("IV") == 4
    assert tn._roman_to_int("A") == "A"

    m = re.match(r"^([IVXLCDM]+)([.-])(\s+)", "IV. ")
    assert tn._repl_roman_heading(m).startswith("4")
    m = re.match(r"^([IVXLCDM]+)([.-])$", "V.")
    assert tn._repl_roman_standalone(m).startswith("5")
    m = re.match(r"^([IVXLCDM]+)$", "VI")
    assert tn._repl_roman_word(m) == "6"


def test_get_sentences_non_ideogram(tn):
    text = f"Hello, world! {TTS_SML['break']} One, two, three, four, five."
    out = tn._get_sentences(text, "en", None)
    assert isinstance(out, list)
    assert TTS_SML["break"] in out


def test_get_sentences_ideogram_real(tn):
    out = tn._get_sentences("你好世界", "zho", None)
    assert isinstance(out, list)
    assert out


def test_get_sentences_error(tn):
    assert tn._get_sentences(None, "en", None) is None


def test_get_date_entities_real(tn, stanza_nlp):
    out = tn._get_date_entities("Today is 2024-01-01", stanza_nlp)
    assert isinstance(out, list)


def test_get_date_entities_error(tn):
    assert tn._get_date_entities("Today", None) is False


def test_set_formatted_number(tn):
    out = tn._set_formatted_number("1,234-5", "en")
    assert out


def test_year2words_branches(tn, tn_no_num2words):
    out = tn._year2words("2001", "en")
    assert isinstance(out, str)
    out = tn_no_num2words._year2words("2001", "en")
    assert isinstance(out, str)
    out = tn._year2words("2005", "en")
    assert isinstance(out, str)


def test_clock2words_wrapper(tn):
    out = tn._clock2words("1:02", "en", None)
    assert isinstance(out, str)


def test_math2words(tn):
    out = tn._math2words("1st 2+3", "en", None)
    assert isinstance(out, str)


def test_math2words_error(tn):
    assert tn._math2words(None, "en", None) is None


def test_roman2number(tn):
    out = tn._roman2number("IV. title")
    assert out.startswith("4.")


def test_filter_sml(tn):
    text = "[break] hello"
    out = tn._filter_sml(text)
    assert TTS_SML["break"] in out


def test_normalize_text_english_and_chinese(tn):
    out = tn.normalize_text("Dr. ok (test)", "en")
    assert isinstance(out, str)
    assert "Okay" in out
    assert '"test"' in out

    input = "你好 (测试)"
    out_cn = tn.normalize_text(input, "zh")
    assert isinstance(out_cn, str)
    print(f"{input} --> {out_cn}")
    assert "\"测试\"" in out_cn
    
    input = "你好!测试80%"
    out_cn = tn.normalize_text(input, "zh")
    assert isinstance(out_cn, str)
    print(f"{input} --> {out_cn}")
    assert "百分之" in out_cn
