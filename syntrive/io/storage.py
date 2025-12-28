"""Storage abstractions for temp and output artifacts."""

class TempStorage:
    def __init__(self, root_dir):
        ...

    def write(self, relative_path, data):
        ...

class OutputStorage:
    def __init__(self, root_dir):
        ...

    def write(self, relative_path, data):
        ...
