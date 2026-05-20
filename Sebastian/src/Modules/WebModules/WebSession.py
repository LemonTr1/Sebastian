from agents import SQLiteSession

def _load_session():
    return SQLiteSession("web_conversation")

_SESSION = _load_session()

def get_web_session():
    return _SESSION