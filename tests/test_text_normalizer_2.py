import pytest
from unittest.mock import patch

from lib.text_normalizer import TextNormalizer
from lib.lang import default_language_code


class TestTextNormalizerResolveLangCodes:
    """
    Test suite for the _resolve_lang_codes static method in the TextNormalizer class.
    """

    @pytest.mark.parametrize("input_lang, expected_iso1, expected_iso3", [
        # Test case 1: Empty/None/Whitespace input should fall back to default
        (None, None, default_language_code),
        ("", None, default_language_code),
        ("  ", None, default_language_code),

        # Test case 2: Valid 2-letter ISO 639-1 codes
        ("en", "en", "eng"),
        ("fr", "fr", "fra"),
        ("de", "de", "deu"),
        ("zh", "zh", "zho"),

        # Test case 3: Valid 3-letter ISO 639-3 codes
        ("eng", "en", "eng"),
        ("fra", "fr", "fra"),
        ("deu", "de", "deu"),
        ("zho", "zh", "zho"),

        # Test case 4: Codes with region tags
        ("zh-cn", "zh", "zho"),
        ("zh-CN", "zh", "zho"),
        ("en-US", "en", "eng"),

        # Test case 5: Uppercase inputs
        ("EN", "en", "eng"),
        ("DEU", "de", "deu"),

        # Test case 6: Inputs with leading/trailing whitespace
        (" en ", "en", "eng"),
        ("  fra  ", "fr", "fra"),

        # Test case 7: Fallback to language_mapping for non-standard codes
        ("azj-script_cyrillic", None, "azj-script_cyrillic"),
        ("cak-dialect_central", None, "cak-dialect_central"),

        # Test case 8: Unknown codes should fall back to default
        ("xyz", None, default_language_code),
        ("abcd", None, default_language_code),
    ])
    def test_resolve_lang_codes_with_iso639(self, input_lang, expected_iso1, expected_iso3):
        """Tests language code resolution when the iso639 library is available."""
        TextNormalizer.resolve_lang_codes.cache_clear()
        iso1, iso3 = TextNormalizer.resolve_lang_codes(input_lang)
        assert iso1 == expected_iso1
        assert iso3 == expected_iso3
        TextNormalizer.resolve_lang_codes.cache_clear()

    @patch.dict('sys.modules', {'iso639': None})
    @pytest.mark.parametrize("input_lang, expected_iso1, expected_iso3", [
        # Test cases when iso639 library is not available
        ("en", "en", "eng"),      # 'en' not in language_mapping keys, fallback to default for iso3
        ("eng", None, "eng"),     # 3-letter code, becomes iso3
        ("de", "de", "eng"),      # 'de' not in language_mapping keys, fallback to default for iso3
        ("deu", None, "deu"),     # 3-letter code, becomes iso3
        ("xyz", None, "eng"),     # unknown, fallback to default
        (None, None, "eng"),      # none, fallback to default
        ("azj-script_cyrillic", None, "azj-script_cyrillic"),  # found in language_mapping
    ])
    def test_resolve_lang_codes_no_iso639(self, input_lang, expected_iso1, expected_iso3):
        """Tests language code resolution when the iso639 library is mocked as unavailable."""
        TextNormalizer.resolve_lang_codes.cache_clear()
        iso1, iso3 = TextNormalizer.resolve_lang_codes(input_lang)
        assert iso1 == expected_iso1
        assert iso3 == expected_iso3
        TextNormalizer.resolve_lang_codes.cache_clear()

    def test_lru_cache_on_resolve_lang_codes(self):
        """Tests that the lru_cache is working as expected."""
        TextNormalizer.resolve_lang_codes.cache_clear()

        # First call, should be a miss
        TextNormalizer.resolve_lang_codes("en")
        assert TextNormalizer.resolve_lang_codes.cache_info().hits == 0
        assert TextNormalizer.resolve_lang_codes.cache_info().misses == 1

        # Second call with same arg, should be a hit
        TextNormalizer.resolve_lang_codes("en")
        assert TextNormalizer.resolve_lang_codes.cache_info().hits == 1
        assert TextNormalizer.resolve_lang_codes.cache_info().misses == 1

        # Third call with different arg, should be a miss
        TextNormalizer.resolve_lang_codes("fr")
        assert TextNormalizer.resolve_lang_codes.cache_info().hits == 1
        assert TextNormalizer.resolve_lang_codes.cache_info().misses == 2

        TextNormalizer.resolve_lang_codes.cache_clear()

