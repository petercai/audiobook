import math
import unicodedata
from functools import lru_cache

import regex as re
from num2words import num2words

from lib.functions import DependencyError
from lib.lang import (
    abbreviations_mapping,
    default_language_code,
    emojis_list,
    language_clock,
    language_mapping,
    language_math_phonemes,
    punctuation_list_set,
    punctuation_split_hard_set,
    punctuation_split_soft_set,
    punctuation_switch,
    resolve_lang_codes,
    roman_numbers_tuples,
    specialchars_mapping,
    specialchars_remove,
)
from lib.models import TTS_SML


class TextNormalizer:
    def __init__(self, lang_iso1=None):
        self.sml_tokens = set(TTS_SML.values())
        self.lang_iso1, self.lang_iso3 = resolve_lang_codes((lang_iso1 or default_language_code).strip())
        self.is_num2words_compat = self._get_num2words_compat(self.lang_iso1)

    @staticmethod
    @lru_cache(maxsize=128)
    def _num2words_lang(lang_iso1):
        if not lang_iso1:
            return "en"
        lang_iso1 = lang_iso1.lower()
        if lang_iso1 in ("zh", "zh-cn", "zh_cn", "zh-hans", "zh-hans-cn"):
            return "zh_CN"
        return lang_iso1

    def get_max_chars(self):
        return language_mapping[self.lang_iso3]['max_chars'] - 4

    def _get_num2words_compat(self, lang_iso1):
        try:
            num2words(1, lang=lang_iso1)
            return True
        except NotImplementedError:
            return False
        except Exception:
            return False

    def normalize_text_4_tts(self, text_block, tts_engine, stanza_nlp):
        # If a Stanza NLP pipeline is available, use it for advanced text processing like date recognition
        if stanza_nlp:
            text_block = self._num2dateWithNLP(
                text_block,
                stanza_nlp,
                tts_engine
            )
        # Convert Roman numerals, clock times, and mathematical expressions to words for better TTS
        text_block = self._roman2number(text_block)  # Convert Roman numerals to Arabic numbers
        text_block = self._clock2words(text_block, tts_engine)  # Convert clock times to words
        text_block = self._math2words(text_block, tts_engine)  # Convert math expressions to words

        # Remove special characters that are not needed for TTS by replacing them with spaces
        specialchars_remove_table = str.maketrans({ch: ' ' for ch in specialchars_remove})
        text_block = text_block.translate(specialchars_remove_table)
        # Perform final text normalization (e.g., handling abbreviations, punctuation) for better TTS quality
        text_block = self.normalize_text(text_block)
        # Split the fully processed text into sentences for TTS based on language-specific rules
        sentences = self.split_sentences(text_block, tts_engine)
        return sentences

    def _num_repl(self, m):
        s = m.group(0)
        # leave years alone (already handled above)
        if re.fullmatch(r"\d{4}", s):
            return s
        n = float(s) if "." in s else int(s)
        if self.is_num2words_compat:
            return num2words(n, lang=self._num2words_lang(self.lang_iso1))
        else:
            return self._math2words(m, None)

    def _num2dateWithNLP(self, text, stanza_nlp, tts_engine):
        # Regex for ordinal numbers (e.g., 1st, 2nd) to convert them to words
        re_ordinal = re.compile(
            r'(?<!\w)(0?[1-9]|[12][0-9]|3[01])(?:\s|\u00A0)*(?:st|nd|rd|th)(?!\w)',
            re.IGNORECASE
        )
        # Regex for general numbers to convert them to words
        re_num = re.compile(r'(?<!\w)[-+]?\d+(?:\.\d+)?(?!\w)')
        # Normalize Unicode characters and replace non-breaking spaces with regular spaces
        text = unicodedata.normalize('NFKC', text).replace('\u00A0', ' ')
        # Process dates if both numbers and ordinals are present in the text
        if re_num.search(text) and re_ordinal.search(text):
            # Use Stanza NLP to identify date entities in the text
            date_spans = self._get_date_entities(text, stanza_nlp)
            if date_spans:
                result = []
                last_pos = 0
                # Process each identified date span
                for start, end, date_text in date_spans:
                    # Add text before the date span to the result
                    result.append(text[last_pos:start])
                    # 1) Convert 4-digit years to words using the _year2words method
                    processed = re.sub(
                        r"\b\d{4}\b",
                        lambda m: self._year2words(m.group()),
                        date_text
                    )
                    # 2) Convert ordinal days to words based on num2words compatibility
                    if self.is_num2words_compat:
                        processed = re_ordinal.sub(
                            lambda m: num2words(int(m.group(1)), to="ordinal", lang=self._num2words_lang(self.lang_iso1)),
                            processed
                        )
                    else:
                        processed = re_ordinal.sub(
                            lambda m: self._math2words(m.group(), tts_engine),
                            processed
                        )
                    # 3) Convert other numbers to words, skipping years which were already processed
                    processed = re_num.sub(lambda m: self._num_repl(m), processed)
                    result.append(processed)
                    last_pos = end
                # Add any remaining text after the last date span
                result.append(text[last_pos:])
                text = ''.join(result)
            else:
                # If no date entities are found, process ordinals and years separately
                if self.is_num2words_compat:
                    text = re_ordinal.sub(
                        lambda m: num2words(int(m.group(1)), to="ordinal", lang=self._num2words_lang(self.lang_iso1)),
                        text
                    )
                else:
                    text = re_ordinal.sub(
                        lambda m: self._math2words(int(m.group(1)), tts_engine),
                        text
                    )
                # Convert 4-digit years to words
                text = re.sub(
                    r"\b\d{4}\b",
                    lambda m: self._year2words(m.group()),
                    text
                )
        return text

    def _split_inclusive(self, text, pattern):
        result = []
        last_end = 0
        for match in pattern.finditer(text):
            result.append(text[last_end:match.end()].strip())
            last_end = match.end()
        if last_end < len(text):
            tail = text[last_end:].strip()
            if tail:
                result.append(tail)
        return result

    def _segment_ideogramms(self, text):
        """
        Tokenizes text for ideogram-based languages, preserving SML tokens.

        This method splits the input text into a list of words or tokens, which is
        a necessary preprocessing step for languages that do not use spaces to
        delimit words (e.g., Chinese, Japanese, Thai). It uses different libraries
        for tokenization based on the specified language.

        Args:
            text (str): The text to be tokenized.

        Returns:
            list: A list of string tokens. If an error occurs during tokenization,
                  it returns a list containing the original text.
        """
        # Create a regex pattern to split the text by SML tokens, while keeping them.
        sml_pattern = "|".join(re.escape(token) for token in self.sml_tokens)
        segments = re.split(f"({sml_pattern})", text)
        result = []
        try:
            for segment in segments:
                if not segment:
                    continue
                # If the segment is an SML token, add it directly to the results.
                if re.fullmatch(sml_pattern, segment):
                    result.append(segment)
                else:
                    # Otherwise, apply the appropriate tokenizer based on the language.
                    if self.lang_iso3 == 'zho':
                        import jieba
                        result.extend([t for t in jieba.cut(segment) if t.strip()])
                    elif self.lang_iso3 == 'jpn':
                        from sudachipy import dictionary, tokenizer
                        sudachi = dictionary.Dictionary().create()
                        mode = tokenizer.Tokenizer.SplitMode.C
                        result.extend([m.surface() for m in sudachi.tokenize(segment, mode) if m.surface().strip()])
                    # elif lang == 'kor':
                    #     from korean_tokenizer import LTokenizer
                    #     ltokenizer = LTokenizer()
                    #     result.extend([t for t in ltokenizer.tokenize(segment) if t.strip()])
                    elif self.lang_iso3 in ['tha', 'lao', 'mya', 'khm']:
                        from pythainlp import word_tokenize
                        result.extend([t for t in word_tokenize(segment, engine='newmm') if t.strip()])
                    else:
                        # If the language is not one of the specified ideogrammatic languages,
                        # treat the segment as a single token.
                        result.append(segment.strip())
            return result
        except Exception as e:
            # If any error occurs (e.g., a tokenizer library is not installed),
            # fall back to returning the original text as a single-item list.
            DependencyError(e)
            return [text]

    def _join_ideogramms(self, idg_list, max_chars):
        """
        Joins a list of ideogrammatic tokens into sentences that respect a maximum
        character length.

        This generator function is designed for languages like Chinese, Japanese, and
        Korean, where text is first tokenized into words. It reconstructs sentences
        from these tokens, ensuring that no single yielded sentence exceeds the
        `max_chars` limit. It also preserves SML tokens as separate items.

        Args:
            idg_list (list): A list of string tokens (words, punctuation, SML tokens).
            max_chars (int): The maximum number of characters allowed per sentence.

        Yields:
            str: A sentence or SML token, formatted and constrained by length.
        """
        try:
            buffer = ''
            for token in idg_list:
                # 1) On SML token: flush the current buffer, then yield the token separately.
                if token.strip() in self.sml_tokens:
                    if buffer:
                        yield buffer
                        buffer = ''
                    yield token
                    continue
                # 2) If adding the next token would overflow the max character limit, flush the current buffer.
                if buffer and len(buffer) + len(token) > max_chars:
                    yield buffer
                    buffer = ''
                # 3) Append the token to the buffer.
                buffer += token
            # 4) After the loop, flush any remaining text in the buffer.
            if buffer:
                yield buffer
        except Exception as e:
            DependencyError(e)
            if buffer:
                yield buffer

    def _repl_abbreviations(self, match: re.Match, mapping) -> str:
        token = match.group(1)
        for k, expansion in mapping.items():
            if token.lower() == k.lower():
                return expansion
        return token  # fallback

    def _n2w(self, n: int, tts_engine) -> str:
        _n2w_cache = {}
        key = (n, self.lang_iso1, self.lang_iso3, self.is_num2words_compat)
        if key in _n2w_cache:
            return _n2w_cache[key]
        if self.is_num2words_compat:
            word = num2words(n, lang=self._num2words_lang(self.lang_iso1))
        else:
            word = self._math2words(n, tts_engine)
        _n2w_cache[key] = word
        return word

    def _repl_clock_num(self, m: re.Match, tts_engine) -> str:
        lc = language_clock.get(self.lang_iso3) if 'language_clock' in globals() else None
        # Parse hh[:mm[:ss]]
        try:
            h = int(m.group(1))
            mnt = int(m.group(2))
            sec = m.group(3)
            sec = int(sec) if sec is not None else None
        except Exception:
            return m.group(0)
        # basic validation; if out of range, keep original
        if not (0 <= h <= 23 and 0 <= mnt <= 59 and (sec is None or 0 <= sec <= 59)):
            return m.group(0)
        # If no language clock rules, just say numbers plainly
        if not lc:
            parts = [self._n2w(h, tts_engine)]
            if mnt != 0:
                parts.append(self._n2w(mnt, tts_engine))
            if sec is not None and sec > 0:
                parts.append(self._n2w(sec, tts_engine))
            return " ".join(parts)

        next_hour = (h + 1) % 24
        special_hours = lc.get("special_hours", {})
        # Build main phrase
        if mnt == 0 and (sec is None or sec == 0):
            if h in special_hours:
                phrase = special_hours[h]
            else:
                phrase = lc["oclock"].format(hour=self._n2w(h, tts_engine))
        elif mnt == 15:
            phrase = lc["quarter_past"].format(hour=self._n2w(h, tts_engine))
        elif mnt == 30:
            # German "halb drei" (= 2:30) uses next hour
            if self.lang_iso3 == "deu":
                phrase = lc["half_past"].format(next_hour=self._n2w(next_hour, tts_engine))
            else:
                phrase = lc["half_past"].format(hour=self._n2w(h, tts_engine))
        elif mnt == 45:
            phrase = lc["quarter_to"].format(next_hour=self._n2w(next_hour, tts_engine))
        elif mnt < 30:
            phrase = lc["past"].format(hour=self._n2w(h, tts_engine), minute=self._n2w(mnt, tts_engine)) if mnt != 0 else lc["oclock"].format(hour=self._n2w(h, tts_engine))
        else:
            minute_to_hour = 60 - mnt
            phrase = lc["to"].format(next_hour=self._n2w(next_hour, tts_engine), minute=self._n2w(minute_to_hour, tts_engine))
        # Append seconds if present
        if sec is not None and sec > 0:
            second_phrase = lc["second"].format(second=self._n2w(sec, tts_engine))
            phrase = lc["full"].format(phrase=phrase, second_phrase=second_phrase)
        return phrase

    def _normalize_commas(self, num_str: str) -> str:
        """Normalize number string to standard comma format: 1,234,567"""
        tok = num_str.replace('\u00A0', '').replace(' ', '')
        if '.' in tok:
            integer_part, decimal_part = tok.split('.', 1)
            integer_part = integer_part.replace(',', '')
            integer_part = "{:,}".format(int(integer_part))
            return f"{integer_part}.{decimal_part}"
        else:
            integer_part = tok.replace(',', '')
            return "{:,}".format(int(integer_part))

    def _clean_single_num(self, num_str):
        max_single_value: int = 999_999_999_999_999_999
        tok = unicodedata.normalize('NFKC', num_str)
        if tok.lower() in ('inf', 'infinity', 'nan'):
            return tok
        clean = tok.replace(',', '').replace('\u00A0', '').replace(' ', '')
        try:
            num = float(clean) if '.' in clean else int(clean)
        except (ValueError, OverflowError):
            return tok
        if not math.isfinite(num) or abs(num) > max_single_value:
            return tok

        # Normalize commas before final output
        tok = self._normalize_commas(tok)

        if self.is_num2words_compat:
            return num2words(num, lang=self._num2words_lang(self.lang_iso1))
        else:
            phoneme_map = language_math_phonemes.get(
                self.lang_iso3,
                language_math_phonemes.get(default_language_code, language_math_phonemes['eng'])
            )
            return ' '.join(phoneme_map.get(ch, ch) for ch in str(num))

    def _clean_formatted_number_match(self, match):
        first_num = self._clean_single_num(match.group(1))
        dash_char = match.group(2) or ''
        second_num = self._clean_single_num(match.group(3)) if match.group(3) else ''
        trailing = match.group(4) or ''
        if second_num:
            return f"{first_num}{dash_char}{second_num}{trailing}"
        else:
            return f"{first_num}{trailing}"

    def _repl_ambiguous(self, match, ambiguous_replacements):
        # handles "num SYMBOL num" and "SYMBOL num"
        if match.group(2) and match.group(2) in ambiguous_replacements:
            return f"{match.group(1)} {ambiguous_replacements[match.group(2)]} {match.group(3)}"
        if match.group(3) and match.group(3) in ambiguous_replacements:
            return f"{ambiguous_replacements[match.group(3)]} {match.group(4)}"
        return match.group(0)

    def __ordinal_to_words(self, m):
        n = int(m.group(1))
        if self.is_num2words_compat:
            try:
                from num2words import num2words
                return num2words(n, to="ordinal", lang=self._num2words_lang(self.lang_iso1))
            except Exception:
                pass
        # If num2words isn't available/compatible, keep original token as-is.
        return m.group(0)

    def _is_valid_roman(self, s):
        valid_roman = re.compile(
            r'^(?=.)M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$',
            re.IGNORECASE
        )
        return bool(valid_roman.fullmatch(s))

    def _roman_to_int(self, s):
        s = s.upper()
        i, result = 0, 0
        while i < len(s):
            for roman, value in roman_numbers_tuples:
                if s[i:i+len(roman)] == roman:
                    result += value
                    i += len(roman)
                    break
            else:
                return s  # Not even a sequence of roman letters
        return result

    def _repl_roman_heading(self, m):
        roman = m.group(1)
        if not self._is_valid_roman(roman):
            return m.group(0)
        val = self._roman_to_int(roman)
        return f"{val}{m.group(2)}{m.group(3)}"

    def _repl_roman_standalone(self, m):
        roman = m.group(1)
        if not self._is_valid_roman(roman):
            return m.group(0)
        val = self._roman_to_int(roman)
        return f"{val}{m.group(2)}"

    def _repl_roman_word(self, m):
        roman = m.group(1)
        if not self._is_valid_roman(roman):
            return m.group(0)
        val = self._roman_to_int(roman)
        return str(val)

    def split_sentences(self, text, tts_engine):
        """
        Splits a given text into a list of sentences based on language-specific rules
        and TTS engine character limits.

        This function is crucial for preparing text for TTS processing by breaking it
        down into manageable chunks that respect punctuation, special markup (SML),
        and character length constraints.

        Args:
            text (str): The input text to be segmented.
            tts_engine: The TTS engine identifier (currently unused in this method but
                        kept for API consistency).

        Returns:
            list: A list of strings, where each string is a sentence or a segment
                  of text suitable for TTS processing. Returns None if an error occurs.
        """
        try:
            # Set the maximum character limit for a sentence, leaving a small buffer.
            max_chars = self.get_max_chars()
            min_tokens = 5  # Minimum number of tokens for certain operations (currently unused).

            # 1. Initial Split by SML tokens (e.g., for breaks and pauses)
            # This ensures that special TTS markup tags are preserved as separate items.
            sml_list = re.split(rf"({'|'.join(map(re.escape, self.sml_tokens))})", text)
            sml_list = [s for s in sml_list if s.strip() or s in self.sml_tokens]

            # 2. Hard Split: Break text at major sentence-ending punctuation.
            # This uses a predefined set of "hard" punctuation marks (e.g., '.', '!', '?').
            pattern_split = '|'.join(map(re.escape, punctuation_split_hard_set))
            pattern = re.compile(rf"(.*?(?:{pattern_split}){''.join(punctuation_list_set)})(?=\s|$)", re.DOTALL)
            hard_list = []
            for s in sml_list:
                # Preserve SML tokens and short segments that are already under the character limit.
                if s in [TTS_SML['break'], TTS_SML['pause']] or len(s) <= max_chars:
                    hard_list.append(s)
                else:
                    # Use a custom split function to keep the delimiters.
                    parts = self._split_inclusive(s, pattern)
                    if parts:
                        for text_part in parts:
                            text_part = text_part.strip()
                            if text_part:
                                hard_list.append(text_part)
                    else:
                        s = s.strip()
                        if s:
                            hard_list.append(s)

            # 3. Soft Split: Further break down long sentences using "soft" punctuation.
            # This handles cases where a sentence is too long for the TTS engine,
            # using commas, semicolons, etc., as breaking points.
            pattern_split = '|'.join(map(re.escape, punctuation_split_soft_set))
            pattern = re.compile(rf"(.*?(?:{pattern_split}))(?=\s|$)", re.DOTALL)
            soft_list = []
            for s in hard_list:
                # Keep SML tokens and segments that are already compliant with the length limit.
                if s in [TTS_SML['break'], TTS_SML['pause']] or len(s) <= max_chars:
                    soft_list.append(s)
                # If a segment is still too long, apply the soft split.
                elif len(s) > max_chars:
                    parts = [p for p in self._split_inclusive(s, pattern) if p]
                    if parts:
                        buffer = ''
                        for idx, part in enumerate(parts):
                            # Predict the length if the next part is added to the buffer.
                            predicted_length = len(buffer) + (1 if buffer else 0) + len(part)
                            # If it fits, add it to the buffer.
                            if predicted_length <= max_chars:
                                buffer = (buffer + ' ' + part).strip() if buffer else part
                            else:
                                # If it doesn't fit, handle the buffer.
                                # Check if the buffer ends with soft punctuation.
                                if buffer and not any(buffer.rstrip().endswith(p) for p in punctuation_split_soft_set):
                                    # If not, try to backtrack to the last punctuation inside the buffer.
                                    last_punct_idx = max((buffer.rfind(p) for p in punctuation_split_soft_set if p in buffer), default=-1)
                                    if last_punct_idx != -1:
                                        # Split at the last found punctuation mark.
                                        soft_list.append(buffer[:last_punct_idx+1].strip())
                                        leftover = buffer[last_punct_idx+1:].strip()
                                        buffer = leftover + ' ' + part if leftover else part
                                    else:
                                        # If no punctuation, split as is.
                                        soft_list.append(buffer.strip())
                                        buffer = part
                                else:
                                    soft_list.append(buffer.strip())
                                    buffer = part
                        # Add any remaining text in the buffer to the list.
                        if buffer:
                            cleaned = re.sub(r'[^\p{L}\p{N} ]+', '', buffer)
                            if any(ch.isalnum() for ch in cleaned):
                                soft_list.append(buffer.strip())
                    else:
                        # If no soft punctuation is found, add the long segment as is.
                        cleaned = re.sub(r'[^\p{L}\p{N} ]+', '', s)
                        if any(ch.isalnum() for ch in cleaned):
                            soft_list.append(s.strip())
                else:
                    # Add segments that are within the length limit.
                    cleaned = re.sub(r'[^\p{L}\p{N} ]+', '', s)
                    if any(ch.isalnum() for ch in cleaned):
                        soft_list.append(s.strip())

            # 4. Language-specific processing for ideogram-based languages.
            # These languages require word tokenization before joining into sentences.
            if self.lang_iso3 in ['zho', 'jpn', 'kor', 'tha', 'lao', 'mya', 'khm']:
                result = []
                for s in soft_list:
                    if s in [TTS_SML['break'], TTS_SML['pause']]:
                        result.append(s)
                    else:
                        # Segment the text into words/tokens.
                        tokens = self._segment_ideogramms(s)
                        if isinstance(tokens, list):
                            result.extend([t for t in tokens if t.strip()])
                        else:
                            tokens = tokens.strip()
                            if tokens:
                                result.append(tokens)
                # Join the tokens back into sentences that respect the max character limit.
                return list(self._join_ideogramms(result, max_chars))
            else:
                # 5. Final segmentation for space-delimited languages.
                # This step ensures that no sentence exceeds the max character limit by splitting
                # at the word level if necessary.
                sentences = []
                for s in soft_list:
                    if s in [TTS_SML['break'], TTS_SML['pause']] or len(s) <= max_chars:
                        sentences.append(s)
                    else:
                        # Split by space and reconstruct sentences within the character limit.
                        words = s.split(' ')
                        text_part = words[0]
                        for w in words[1:]:
                            if len(text_part) + 1 + len(w) <= max_chars:
                                text_part += ' ' + w
                            else:
                                text_part = text_part.strip()
                                if text_part:
                                    sentences.append(text_part)
                                text_part = w
                        # Add the last remaining part of the sentence.
                        if text_part:
                            cleaned = re.sub(r'[^\p{L}\p{N} ]+', '', text_part).strip()
                            if not any(ch.isalnum() for ch in cleaned):
                                continue
                            sentences.append(text_part)
                return sentences
        except Exception as e:
            error = f'get_sentences() error: {e}'
            print(error)
            return None

    def _get_date_entities(self, text, stanza_nlp):
        try:
            doc = stanza_nlp(text)
            date_spans = []
            for ent in doc.ents:
                if ent.type == 'DATE':
                    date_spans.append((ent.start_char, ent.end_char, ent.text))
            return date_spans
        except Exception as e:
            error = f'get_date_entities() error: {e}'
            print(error)
            return False

    def _set_formatted_number(self, text: str, max_single_value: int = 999_999_999_999_999_999):
        # match up to 18 digits, optional ",." groups (allowing spaces or NBSP after comma), optional decimal of up to 12 digits
        # handle optional range with dash/en dash/em dash between numbers, and allow trailing punctuation
        number_re = re.compile(
            r'(?<!\w)'
            r'(\d{1,18}(?:,\s*\d{1,18})*(?:\.\d{1,12})?)'      # first number
            r'(?:\s*([---])\s*'                                # dash type
            r'(\d{1,18}(?:,\s*\d{1,18})*(?:\.\d{1,12})?))?'    # optional second number
            r'([^\w\s]*)',                                     # optional trailing punctuation
            re.UNICODE
        )

        return number_re.sub(lambda m: self._clean_formatted_number_match(m), text)

    def _year2words(self, year_str):
        try:
            year = int(year_str)
            first_two = int(year_str[:2])
            last_two = int(year_str[2:])
            lang_iso3 = self.lang_iso3 if self.lang_iso3 in language_math_phonemes.keys() else default_language_code
            if not year_str.isdigit() or len(year_str) != 4 or last_two < 10:
                if self.is_num2words_compat:
                    return num2words(year, lang=self._num2words_lang(self.lang_iso1))
                else:
                    return ' '.join(language_math_phonemes[lang_iso3].get(ch, ch) for ch in year_str)
            if self.is_num2words_compat:
                return f"{num2words(first_two, lang=self._num2words_lang(self.lang_iso1))} {num2words(last_two, lang=self._num2words_lang(self.lang_iso1))}"
            else:
                return ' '.join(language_math_phonemes[lang_iso3].get(ch, ch) for ch in first_two) + ' ' + ' '.join(language_math_phonemes[lang_iso3].get(ch, ch) for ch in last_two)
        except Exception as e:
            error = f'year2words() error: {e}'
            print(error)
            raise
            return False

    def _clock2words(self, text, tts_engine):
        time_rx = re.compile(r'(\d{1,2})[:.](\d{1,2})(?:[:.](\d{1,2}))?')
        return time_rx.sub(lambda m: self._repl_clock_num(m, tts_engine), text)

    def _math2words(self, text, tts_engine):
        """
        Normalize math-like tokens into spoken-friendly words.

        This routine prepares mathematical expressions and numbers for TTS by:
        - Converting ordinal forms like "1st", "2nd", "3rd", "4th" to words when
          num2words is compatible for the target language.
        - Expanding standalone symbols (e.g., "+", "=", "%") into their phoneme
          equivalents using language_math_phonemes, while skipping digits and
          the comma/period separators.
        - Handling ambiguous symbols ("-", "/", "*", "x") only when they appear
          in equation-like contexts such as "12-5" or "-7"; this avoids changing
          hyphens and slashes used in normal prose.
        - Normalizing formatted numbers and number ranges (commas, decimals, and
          optional dash-separated ranges) before applying final number-to-words
          conversion with _set_formatted_number.
        """
        try:
            # Matches any digits + optional space/NBSP + st/nd/rd/th, not glued into words.
            re_ordinal = re.compile(r'(?<!\w)(\d+)(?:\s|\u00A0)*(?:st|nd|rd|th)(?!\w)')
            text = re.sub(r'(\d)\)', r'\1 : ', str(text))
            text = re_ordinal.sub(lambda m: self.__ordinal_to_words(m), text)
            # Symbol phonemes
            ambiguous_symbols = {"-", "/", "*", "x"}
            phonemes_list = language_math_phonemes.get(self.lang_iso3, language_math_phonemes[default_language_code])
            replacements = {k: v for k, v in phonemes_list.items() if not k.isdigit() and k not in [',', '.']}
            normal_replacements = {k: v for k, v in replacements.items() if k not in ambiguous_symbols}
            ambiguous_replacements = {k: v for k, v in replacements.items() if k in ambiguous_symbols}
            # Replace unambiguous symbols everywhere
            if normal_replacements:
                sym_pat = r'(' + '|'.join(map(re.escape, normal_replacements.keys())) + r')'
                text = re.sub(sym_pat, lambda m: f" {normal_replacements[m.group(1)]} ", text)
            # Replace ambiguous symbols only in valid equation contexts
            if ambiguous_replacements:
                ambiguous_pattern = (
                    r'(?<!\S)'                   # no non-space before
                    r'(\d+)\s*([-/*x])\s*(\d+)'  # num SYMBOL num
                    r'(?!\S)'                    # no non-space after
                    r'|'                         # or
                    r'(?<!\S)([-/*x])\s*(\d+)(?!\S)'  # SYMBOL num
                )
                text = re.sub(ambiguous_pattern, lambda m: self._repl_ambiguous(m, ambiguous_replacements), text)
            text = self._set_formatted_number(text)
        except Exception as e:
            error = f'_math2words() error: {e} for input: {text}'
            DependencyError(error)
            return text
        return text

    def _roman2number(self, text):
        # Your heading/standalone rules stay
        text = re.sub(r'^(?:\s*)([IVXLCDM]+)([.-])(\s+)', self._repl_roman_heading, text, flags=re.MULTILINE)
        text = re.sub(r'^(?:\s*)([IVXLCDM]+)([.-])(?:\s*)$', self._repl_roman_standalone, text, flags=re.MULTILINE)

        # NEW: only convert whitespace-delimited tokens of length >= 2
        # This avoids: 19C, 19øC, øC, AC/DC, CD-ROM, single-letter "I"
        text = re.sub(r'(?<!\S)([IVXLCDM]{2,})(?!\S)', self._repl_roman_word, text)

        return text

    def _filter_sml(self, text):
        for key, value in TTS_SML.items():
            pattern = re.escape(key) if key == '###' else r'\[' + re.escape(key) + r'\]'
            text = re.sub(pattern, f" {value} ", text)
        return text

    def normalize_text(self, text):
        """
        Normalize general text and apply language-specific cleanup for TTS.

        English-only behavior:
        - Uppercases dotted acronyms (e.g., "c.i.a." -> "CIA").
        - Replaces standalone "ok" with "Okay".

        Language-dependent behavior (uses instance language -> ISO-639-3 mapping):
        - Expands abbreviations via abbreviations_mapping when available for the language.
        - Replaces special characters with spoken equivalents via specialchars_mapping.

        Language-agnostic behavior (applied to all languages):
        - Removes emojis.
        - Preserves SML tags by converting bracketed tokens to TTS markup.
        - Collapses multi-line breaks into pause tokens and replaces single newlines with spaces.
        - Normalizes punctuation variants using punctuation_switch.
        - Converts NBSP to spaces and collapses repeated whitespace.
        - Converts parenthetical phrases to quoted phrases.
        - Reduces repeated hard/soft punctuation to a single instance.
        - Inserts a space between letters and numbers in mixed tokens.
        """
        # Remove emojis
        emoji_pattern = re.compile(f"[{''.join(emojis_list)}]+", flags=re.UNICODE)
        emoji_pattern.sub('', text)
        if self.lang_iso3 in abbreviations_mapping:
            mapping = abbreviations_mapping[self.lang_iso3]
            # Sort keys by descending length so longer ones match first
            keys = sorted(mapping.keys(), key=len, reverse=True)
            # Build a regex that only matches whole "words" (tokens) exactly
            pattern = re.compile(
                r'(?<!\w)(' + '|'.join(re.escape(k) for k in keys) + r')(?!\w)',
                flags=re.IGNORECASE
            )
            text = pattern.sub(lambda m: self._repl_abbreviations(m, mapping), text)
        # This regex matches sequences like a., c.i.a., f.d.a., m.c., etc...
        pattern = re.compile(r'\b(?:[a-zA-Z]\.){1,}[a-zA-Z]?\b\.?')
        # uppercase acronyms
        text = re.sub(r'\b(?:[a-zA-Z]\.){1,}[a-zA-Z]?\b\.?', lambda m: m.group().replace('.', '').upper(), text)
        # Prepare SML tags
        text = self._filter_sml(text)
        # Replace multiple newlines ("\n\n", "\r\r", "\n\r", etc.) with a ØpauseØ 1.4sec
        pattern = r'(?:\r\n|\r|\n){2,}'
        text = re.sub(pattern, f" {TTS_SML['pause']} ", text)
        # Replace single newlines ("\n" or "\r") with spaces
        text = re.sub(r'\r\n|\r|\n', ' ', text)
        # Replace punctuations causing hallucinations
        pattern = f"[{''.join(map(re.escape, punctuation_switch.keys()))}]"
        text = re.sub(pattern, lambda match: punctuation_switch.get(match.group(), match.group()), text)
        # Replace NBSP with a normal space
        text = text.replace("\xa0", " ")
        # Replace multiple and spaces with single space
        text = re.sub(r'\s+', ' ', text)
        # Replace ok by 'Owkey'
        text = re.sub(r'\bok\b', 'Okay', text, flags=re.IGNORECASE)
        # Replace parentheses with double quotes
        text = re.sub(r'\(([^)]+)\)', r'"\1"', text)
        # Escape special characters in the punctuation list for regex
        pattern = '|'.join(map(re.escape, punctuation_split_hard_set))
        # Reduce multiple consecutive punctuations
        text = re.sub(rf'(\s*({pattern})\s*)+', r'\2 ', text).strip()
        # Escape special characters in the punctuation list for regex
        pattern = '|'.join(map(re.escape, punctuation_split_soft_set))
        # Reduce multiple consecutive punctuations
        text = re.sub(rf'(\s*({pattern})\s*)+', r'\2 ', text).strip()
        # Pattern 1: Add a space between UTF-8 characters and numbers
        text = re.sub(r'(?<=[\p{L}])(?=\d)|(?<=\d)(?=[\p{L}])', ' ', text)
        # Replace special chars with words
        specialchars = specialchars_mapping.get(self.lang_iso3, specialchars_mapping.get(default_language_code, specialchars_mapping['eng']))
        specialchars_table = {ord(char): f" {word} " for char, word in specialchars.items()}
        text = text.translate(specialchars_table)
        text = ' '.join(text.split())
        return text
