
import json
import uuid
from types import SimpleNamespace

def to_object(data):
    if isinstance(data, dict):
        return SimpleNamespace(**{k: to_object(v) for k, v in data.items()})
    elif isinstance(data, list):
        return [to_object(v) for v in data]
    else:
        return data

class SessionContextMock:
    def __init__(self, args):
        self.sessions = {}
        id = args["session"] if args["session"] is not None else str(uuid.uuid4())
        self.sessions[id] = args

    def get_session(self, id):
        return self.sessions[id]

class Session(SimpleNamespace):
    """Recursively converts dicts/lists to objects with dot access."""

    def __init__(self, data):
        """
        Initialize a Session object from a dictionary.
        
        :param data: A dictionary of key-value pairs to initialize the session.
        :type data: dict
        """
        
        for key, value in data.items():
            setattr(self, key, self._wrap(value))

    @classmethod
    def _wrap(cls, value):
        if isinstance(value, dict):
            return cls(value)
        elif isinstance(value, list):
            return [cls._wrap(v) for v in value]
        else:
            return value

    def to_dict(self):
        """Recursively convert back to dict."""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, Session):
                result[key] = value.to_dict()
            elif isinstance(value, list):
                result[key] = [v.to_dict() if isinstance(v, Session) else v for v in value]
            else:
                result[key] = value
        return result

    # def to_json(self, **kwargs):
    #     """Convert back to JSON string."""
    #     return json.dumps(self.to_dict(), **kwargs)

    # @classmethod
    # def from_json(cls, json_str):
    #     """Create object directly from JSON string."""
    #     return cls(json.loads(json_str))
