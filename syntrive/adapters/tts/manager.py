"""TTS manager that selects engines by configuration."""

class TTSManager:
    def __init__(self, registry=None):
        ...

    def get_engine(self, tts_config):
        ...
