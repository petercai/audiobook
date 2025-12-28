"""Path resolution for intermediate and final artifacts."""

class PathResolver:
    def __init__(self, base_dir, temp_dir=None):
        ...

    def chapter_dir(self, chapter_index):
        ...

    def segment_audio_path(self, chapter_index, segment_index, audio_format):
        ...

    def chapter_audio_path(self, chapter_index, audio_format):
        ...

    def subtitle_path(self, chapter_index, subtitle_format):
        ...
