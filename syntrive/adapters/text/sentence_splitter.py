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
    rf"(.*?(?:{_HARD_SPLIT}){''.join(punctuation_list_set)})(?=\s|$)",
    re.DOTALL,
)
_SOFT_SPLIT = "|".join(map(re.escape, punctuation_split_soft_set))
_SOFT_PATTERN = re.compile(
    rf"(.*?(?:{_SOFT_SPLIT}))(?=\s|$)",
    re.DOTALL,
)
_SOFT_PUNCT = tuple(punctuation_split_soft_set)


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

    def split(self, paragraph, language):
        # if language == "en":
        #     return self.split_with_pysbd(paragraph, language)
        """
        Split text into TTS-friendly sentences while preserving SML tokens.
        """
        try:
            if paragraph is None:
                return None
            if not paragraph:
                return []

            _, lang_iso3 = resolve_lang_codes((language or default_language_code).strip())
            max_chars = self._get_max_chars(lang_iso3)

            sml_list = _SML_PATTERN.split(paragraph)
            sml_list = [s for s in sml_list if s.strip() or s in self.sml_tokens]

            hard_list = []
            for s in sml_list:
                if s in (TTS_SML['break'], TTS_SML['pause']) or len(s) <= max_chars:
                    hard_list.append(s)
                else:
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
                if s in (TTS_SML['break'], TTS_SML['pause']) or len(s) <= max_chars:
                    soft_list.append(s)
                elif len(s) > max_chars:
                    parts = [p for p in self._split_inclusive(s, _SOFT_PATTERN) if p]
                    if parts:
                        buffer = ''
                        for part in parts:
                            predicted_length = len(buffer) + (1 if buffer else 0) + len(part)
                            if predicted_length <= max_chars:
                                buffer = (buffer + ' ' + part).strip() if buffer else part
                            else:
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
            print(error)
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
        sml_pattern = "|".join(re.escape(token) for token in self.sml_tokens)
        segments = re.split(f"({sml_pattern})", text)
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
