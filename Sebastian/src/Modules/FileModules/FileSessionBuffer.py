from typing import List
import threading

class FileSessionBuffer:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._buf = []
        return cls._instance

    def write(self, item: dict) -> None:
        with self._lock:
            self._buf.append(item)

    def read_all(self) -> List[dict]:
        with self._lock:
            return self._buf.copy()  # 返回副本，避免外部直接篡改

    def clear(self) -> None:
        with self._lock:
            self._buf.clear()

# 全局唯一实例
file_session_buffer = FileSessionBuffer()