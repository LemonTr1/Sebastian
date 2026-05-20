from agents import SQLiteSession

def _load_session():
    return SQLiteSession("code_conversation")

_SESSION = _load_session()

def get_code_session():
    return _SESSION