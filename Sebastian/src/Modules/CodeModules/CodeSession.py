import asyncio
from agents import SQLiteSession

def _load_session():
    return SQLiteSession("code_conversation")

_SESSION = _load_session()

_code_session_lock = asyncio.Lock()

def get_code_session():
    return _SESSION

def get_code_session_lock():
    """返回模块级锁，供外部包裹 Runner.run 使用"""
    return _code_session_lock