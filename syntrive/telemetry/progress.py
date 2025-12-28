"""Progress reporting for long-running tasks."""

class ProgressReporter:
    def __init__(self, total=None):
        ...

    def update(self, current, message=None):
        ...
