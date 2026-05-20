from agents import SQLiteSession

def _load_session():
    return SQLiteSession("file_conversation")

_SESSION = _load_session()

def get_file_session():
    return _SESSION