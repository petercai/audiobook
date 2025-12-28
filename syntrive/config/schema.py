"""Configuration schema for processing and synthesis."""

class ProcessingConfig:
    def __init__(self, language, segment_rules, tts_config, output_rules):
        ...

class SegmentRules:
    def __init__(self, max_words=None, max_chars=None):
        ...

class OutputRules:
    def __init__(self, formats, split_duration_minutes=None):
        ...

class TtsConfig:
    def __init__(self, engine_name, engine_options=None, voice=None):
        ...
