"""Audio artifact persistence for segments and chapters."""

class SegmentAudioWriter:
    def __init__(self, storage, path_resolver, audio_format='flac'):
        ...

    def write_segment(self, chapter_index, segment_index, audio_bytes):
        ...
