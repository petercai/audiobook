"""Base TTS engine adapter contract."""

class BaseTTSEngine:
    def __init__(self, options=None):
        ...

    def synthesize(self, text, voice=None):
        ...
