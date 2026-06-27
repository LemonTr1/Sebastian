import os


def get_username() -> str:
    return os.environ.get("USER") or os.environ.get("LOGNAME") or os.getlogin()
