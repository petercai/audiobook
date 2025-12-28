"""Registry for stage discovery and configuration wiring."""

class StageRegistry:
    def __init__(self):
        ...

    def register(self, name, stage_cls):
        ...

    def create(self, name, **kwargs):
        ...
