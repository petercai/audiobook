"""Sentence splitting adapter."""

import regex as re

from lib.lang import (
    default_language_code,
    language_mapping,
    punctuation_list_set,
    punctuation_split_hard_set,
    punctuation_split_soft_set,
    resolve_lang_codes,
)
from lib.models import TTS_SML
from lib.util import util

_SML_TOKENS = set(TTS_SML.values())
_SML_PATTERN = re.compile(rf"({'|'.join(map(re.escape, _SML_TOKENS))})")

_HARD_SPLIT = "|".join(map(re.escape, punctuation_split_hard_set))
_HARD_PATTERN = re.compile(
    # rf"" is a raw f-string: `r` keeps backslashes literal for the regex engine,
    # `f` interpolates `{_HARD_SPLIT}` and `{''.join(punctuation_list_set)}` at build time.
    # Pattern breakdown:
    # - (.*?(?:{_HARD_SPLIT})...): capture the shortest text ending with a hard-split char.
    # - [{''.join(map(re.escape, punctuation_list_set))}]*: match zero or more trailing punctuation chars.
        # Using re.escape on each character to ensure special regex characters (like ., ?, -) are treated literally.
        # Wrapping the result in [...] to create a character class.
        # Adding * to allow matching zero or more of these trailing punctuation characters.    
    # - (?=\\s|$): stop only before whitespace or end-of-string.
    # Hard split chars (punctuation_split_hard_set):
    #   . ! ? \u2026 \uFF01 \uFF1F \u061F \u1367 \u203D \u1362 \u3002 \u0964 \u0965 \u0F0D \u17D4 \u17D5
    # Trailing punctuation_list_set chars (literal sequence of this set's members):
    #   . ! ? , : ; " - \u00A1 \u00BF \u00AB \u00BB \u00B7 \u05F4 \u060C \u061B \u061F \u0964 \u0965
    #   \u0E2F \u0ECC \u0ECD \u0F0D \u0F0E \u1361 \u1362 \u1363 \u1364 \u1365 \u1366 \u1367 \u17D4 \u17D5
    #   \u2014 \u2026 \u3001 \u3002 \uFF0C \uFF1A \uFF1B \uFF01 \uFF1F
    rf"(.*?(?:{_HARD_SPLIT})[{''.join(map(re.escape, punctuation_list_set))}]*)(?=\s|$)",
    re.DOTALL,
)

_SOFT_SPLIT = "|".join(map(re.escape, punctuation_split_soft_set))
_SOFT_PATTERN = re.compile(
    rf"(.*?(?:{_SOFT_SPLIT}))(?=\s|$)",
    re.DOTALL,
)
_SOFT_PUNCT = tuple(punctuation_split_soft_set)
# todo: explain _CLEAN_ALNUM_PATTERN with all details and put into inline comments. what r"[^\p{L}\p{N} ]+" means? list all final match chars in inline comments
_CLEAN_ALNUM_PATTERN = re.compile(r"[^\p{L}\p{N} ]+")


class SentenceSplitter:
    def __init__(self, rules=None):
        self.rules = rules
        self.sml_tokens = _SML_TOKENS
        
    def split_with_pysbd(self, paragraph, language):
        if paragraph is None:
            return None
        if not paragraph:
            return []
        try:
            import pysbd
            if isinstance(self.rules, dict):
                segmenter = pysbd.Segmenter(**self.rules)
            else:
                segmenter = pysbd.Segmenter(language=language, clean=False)
            return [s for s in segmenter.segment(paragraph) if s]
        except Exception as e:
            util.print_error(e)
            return [paragraph]

    def split_zh(self, paragraph, lang_iso3, max_chars):
        try:
            # split long text on hard/soft punctuation (inclusive).
            segmentation_list = self.hard_punctuation_split(paragraph)
            segmentation_list = self.soft_punctuation_split(segmentation_list, max_chars)
            # if lang_iso3 in ['zho', 'jpn', 'kor', 'tha', 'lao', 'mya', 'khm']:
            #     return self.split_for_ideographic(segmentation_list, lang_iso3, max_chars)
            return segmentation_list
        except Exception as e:
            error = f'sentence_splitter() error: {e}'
            util.print_error(e, error)
            return None

    def soft_punctuation_split(self, sentences_list, max_chars):
        """
        Split long sentences on soft punctuation and repack greedily to max_chars.

        This method keeps punctuation with its preceding text, then merges pieces
        into the largest chunks possible without exceeding max_chars. It also
        drops fragments that contain no alphanumeric characters (punctuation-only).
        """
        # Local bindings for speed inside the tight loop.
        soft_pattern = _SOFT_PATTERN
        soft_punct = _SOFT_PUNCT
        clean_re = _CLEAN_ALNUM_PATTERN
        split_list = []
        append_out = split_list.append

        def _has_alnum(text):
            # Remove punctuation, then check for any alphanumeric content.
            cleaned = clean_re.sub("", text)
            return any(ch.isalnum() for ch in cleaned)

        for s in sentences_list:
            # Skip the expensive split for already short sentences.
            if len(s) <= max_chars:
                if _has_alnum(s):
                    append_out(s.strip())
                continue

            # Split on soft punctuation and keep the punctuation attached.
            parts = [p for p in self._split_inclusive(s, soft_pattern) if p]
            if not parts:
                if _has_alnum(s):
                    append_out(s.strip())
                continue

            # Greedily pack parts back together up to max_chars.
            buffer = ""
            for part in parts:
                predicted_length = len(buffer) + (1 if buffer else 0) + len(part)
                if predicted_length <= max_chars:
                    # Still fits: extend the current buffer.
                    buffer = (buffer + " " + part).strip() if buffer else part
                    continue

                # Would overflow: try to split at the last soft punctuation.
                if buffer and not buffer.rstrip().endswith(soft_punct):
                    last_punct_idx = max(
                        (buffer.rfind(p) for p in soft_punct if p in buffer),
                        default=-1,
                    )
                    if last_punct_idx != -1:
                        # Emit up to the last soft punctuation and carry leftover.
                        append_out(buffer[:last_punct_idx + 1].strip())
                        leftover = buffer[last_punct_idx + 1:].strip()
                        buffer = f"{leftover} {part}".strip() if leftover else part
                        continue

                # Fallback: emit the buffer as-is and start a new one with part.
                append_out(buffer.strip())
                buffer = part

            # Flush remaining buffer if it contains alphanumeric content.
            if buffer and _has_alnum(buffer):
                append_out(buffer.strip())

        return split_list

    def split_for_ideographic(self, sentences_list, lang_iso3, max_chars):
        result = []
        # ideographic segmentation（表意语音句子分割） + packing by max_chars.
        for s in sentences_list:
            tokens = self._segment_ideogramms(s, lang_iso3)
            if isinstance(tokens, list):
                result.extend([t for t in tokens if t.strip()])
            else:
                tokens = tokens.strip()
                if tokens:
                    result.append(tokens)
        return list(self._join_ideogramms(result, max_chars))

    def hard_punctuation_split(self, paragraph):
        hard_list = []
        parts = self._split_inclusive(paragraph, _HARD_PATTERN)
        if parts:
            for text_part in parts:
                text_part = text_part.strip()
                if text_part:
                    hard_list.append(text_part)
        else:
            s = paragraph.strip()
            if s:
                hard_list.append(s)
        return hard_list

    def split(self, paragraph, language):
        if paragraph is None:
            return None
        if not paragraph:
            return []
        
        _, lang_iso3 = resolve_lang_codes((language or default_language_code).strip())
        max_chars = self._get_max_chars(lang_iso3)
        
        if language == "zh":
            return self.split_zh(paragraph, lang_iso3, max_chars)
        
        return self.split_en(paragraph, lang_iso3, max_chars)

    def split_en(self, paragraph, lang_iso3, max_chars):
        """
        Split text into TTS-friendly sentences while preserving SML tokens.

        The algorithm runs in phases to keep each output below the per-language
        `max_chars` limit while avoiding unnatural breaks:
        1) Preserve SML tokens: split input by SML markers so they can be kept as
           atomic tokens and never merged into text.
        2) Hard punctuation pass: for long text chunks, split on hard sentence
           boundaries (e.g., "." "!" "?") while keeping the punctuation with
           the sentence.
        3) Soft punctuation pass: for still-long chunks, split on soft
           punctuation (e.g., "," ";" ":") and then greedily pack parts back
           together up to `max_chars` to avoid overly short fragments.
        4) Language-specific handling: for ideographic languages, run word
           segmentation and re-pack tokens by `max_chars`.
        5) Final word-wrap pass: for alphabetic languages, split long strings by
           spaces into `max_chars` sized chunks.
        """
        try:
            # Phase 1: split by SML tokens so they remain as standalone items.
            sml_list = _SML_PATTERN.split(paragraph)
            sml_list = [s for s in sml_list if s.strip() or s in self.sml_tokens]

            hard_list = []
            for s in sml_list:
                # Keep SML tokens and already-short text as-is.
                if s in (TTS_SML['break'], TTS_SML['pause']) or len(s) <= max_chars:
                    hard_list.append(s)
                else:
                    # Phase 2: split long text on hard punctuation (inclusive).
                    parts = self._split_inclusive(s, _HARD_PATTERN)
                    if parts:
                        for text_part in parts:
                            text_part = text_part.strip()
                            if text_part:
                                hard_list.append(text_part)
                    else:
                        s = s.strip()
                        if s:
                            hard_list.append(s)

            soft_list = []
            for s in hard_list:
                # Keep SML tokens and short sentences without changes.
                if s in (TTS_SML['break'], TTS_SML['pause']) or len(s) <= max_chars:
                    soft_list.append(s)
                elif len(s) > max_chars:
                    # Phase 3: split on soft punctuation, then re-pack greedily.
                    parts = [p for p in self._split_inclusive(s, _SOFT_PATTERN) if p]
                    if parts:
                        buffer = ''
                        for part in parts:
                            predicted_length = len(buffer) + (1 if buffer else 0) + len(part)
                            if predicted_length <= max_chars:
                                # Append current part into the running buffer.
                                buffer = (buffer + ' ' + part).strip() if buffer else part
                            else:
                                # Buffer would overflow: try to split at last soft punct.
                                if buffer and not buffer.rstrip().endswith(_SOFT_PUNCT):
                                    last_punct_idx = max(
                                        (buffer.rfind(p) for p in _SOFT_PUNCT if p in buffer),
                                        default=-1,
                                    )
                                    if last_punct_idx != -1:
                                        soft_list.append(buffer[:last_punct_idx + 1].strip())
                                        leftover = buffer[last_punct_idx + 1:].strip()
                                        buffer = f"{leftover} {part}".strip() if leftover else part
                                    else:
                                        soft_list.append(buffer.strip())
                                        buffer = part
                                else:
                                    soft_list.append(buffer.strip())
                                    buffer = part
                        if buffer:
                            # Drop fragments that are only punctuation/whitespace.
                            cleaned = re.sub(r'[^\p{L}\p{N} ]+', '', buffer)
                            if any(ch.isalnum() for ch in cleaned):
                                soft_list.append(buffer.strip())
                    else:
                        cleaned = re.sub(r'[^\p{L}\p{N} ]+', '', s)
                        if any(ch.isalnum() for ch in cleaned):
                            soft_list.append(s.strip())
                else:
                    cleaned = re.sub(r'[^\p{L}\p{N} ]+', '', s)
                    if any(ch.isalnum() for ch in cleaned):
                        soft_list.append(s.strip())

            if lang_iso3 in ['zho', 'jpn', 'kor', 'tha', 'lao', 'mya', 'khm']:
                # Phase 4: ideographic segmentation + packing by max_chars.
                result = []
                for s in soft_list:
                    if s in (TTS_SML['break'], TTS_SML['pause']):
                        result.append(s)
                    else:
                        tokens = self._segment_ideogramms(s, lang_iso3)
                        if isinstance(tokens, list):
                            result.extend([t for t in tokens if t.strip()])
                        else:
                            tokens = tokens.strip()
                            if tokens:
                                result.append(tokens)
                return list(self._join_ideogramms(result, max_chars))

            # Phase 5: for alphabetic languages, split long items by spaces.
            sentences = []
            for s in soft_list:
                if s in (TTS_SML['break'], TTS_SML['pause']) or len(s) <= max_chars:
                    sentences.append(s)
                else:
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
                    if text_part:
                        cleaned = re.sub(r'[^\p{L}\p{N} ]+', '', text_part).strip()
                        if not any(ch.isalnum() for ch in cleaned):
                            continue
                        sentences.append(text_part)
            return sentences
        except Exception as e:
            error = f'sentence_splitter() error: {e}'
            util.print_error(e, error)
            return None

    @staticmethod
    def _get_max_chars(lang_iso3):
        lang_key = lang_iso3 if lang_iso3 in language_mapping else default_language_code
        return language_mapping[lang_key]['max_chars'] - 4

    @staticmethod
    def _split_inclusive(text, pattern):
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

    @staticmethod
    def _clean_paragraph_text(paragraph_text_list, max_chars):
        break_token = TTS_SML['break']
        pause_token = TTS_SML['pause']
        clean_list = []
        i = 0
        n = len(paragraph_text_list)
        while i < n:
            current = paragraph_text_list[i]
            if current == break_token and clean_list:
                prev = clean_list[-1]
                if prev == break_token or prev == pause_token:
                    i += 1
                    continue
                if prev and (prev[-1].isalnum() or prev[-1] == ' '):
                    if i + 1 < n:
                        next_sentence = paragraph_text_list[i + 1]
                        merged_length = len(prev.rstrip()) + 1 + len(next_sentence.lstrip())
                        if merged_length <= max_chars:
                            if not prev.endswith(" ") and not next_sentence.startswith(" "):
                                clean_list[-1] = prev + " " + next_sentence
                            else:
                                clean_list[-1] = prev + next_sentence
                            i += 2
                            continue
                        clean_list.append(current)
                        i += 1
                        continue
            clean_list.append(current)
            i += 1
        return clean_list

    def _segment_ideogramms(self, text, lang_iso3):
        """
        DOSN'T work well - too aggresive!!
        Segments ideographic text (e.g., Chinese, Japanese) into words or meaningful units.

        This method handles SML tokens by preserving them as standalone segments.
        For actual text content, it uses language-specific libraries for word segmentation.

        Args:
            text (str): The input text containing ideographic characters and potentially SML tokens.
            lang_iso3 (str): The ISO 639-3 language code (e.g., 'zho' for Chinese, 'jpn' for Japanese).

        Returns:
            list[str]: A list of segmented words, phrases, or SML tokens.
                       If an error occurs during segmentation, the original text is returned
                       as a single-element list.
        """
        # Define a regex pattern to split the text by SML tokens.
        # This ensures that SML tokens are treated as distinct segments and not
        # processed by the language-specific segmenters.
        sml_pattern: str = "|".join(re.escape(token) for token in self.sml_tokens)
        # Split the text, keeping the SML tokens as part of the result.
        segments: list[str] = re.split(f"({sml_pattern})", text)
        result: list[str] = []
        
        result = []
        try:
            for segment in segments:
                if not segment:
                    continue
                if re.fullmatch(sml_pattern, segment):
                    result.append(segment)
                else:
                    if lang_iso3 == 'zho':
                        import jieba
                        result.extend([t for t in jieba.cut(segment) if t.strip()])
                    elif lang_iso3 == 'jpn':
                        from sudachipy import dictionary, tokenizer
                        sudachi = dictionary.Dictionary().create()
                        mode = tokenizer.Tokenizer.SplitMode.C
                        result.extend([m.surface() for m in sudachi.tokenize(segment, mode) if m.surface().strip()])
                    elif lang_iso3 in ['tha', 'lao', 'mya', 'khm']:
                        from pythainlp import word_tokenize
                        result.extend([t for t in word_tokenize(segment, engine='newmm') if t.strip()])
                    else:
                        result.append(segment.strip())
            return result
        except Exception as e:
            util.print_error(e)
            return [text]

    def _join_ideogramms(self, idg_list, max_chars):
        try:
            buffer = ''
            for token in idg_list:
                if token.strip() in self.sml_tokens:
                    if buffer:
                        yield buffer
                        buffer = ''
                    yield token
                    continue
                if buffer and len(buffer) + len(token) > max_chars:
                    yield buffer
                    buffer = ''
                buffer += token
            if buffer:
                yield buffer
        except Exception as e:
            util.print_error(e)
            if buffer:
                yield buffer
