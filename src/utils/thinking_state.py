"""会话级思考强度状态（仅当前会话生效，不写 .env）。"""
import threading

from src.utils.thinking import LEVELS


class ThinkingState:
    def __init__(self, level: str = "medium"):
        if level not in LEVELS:
            raise ValueError(f"未知思考强度：{level}")
        self._level = level
        self._lock = threading.Lock()

    def snapshot(self) -> str:
        with self._lock:
            return self._level

    def set(self, level: str) -> None:
        if level not in LEVELS:
            raise ValueError(f"未知思考强度：{level}")
        with self._lock:
            self._level = level


# 启动默认中等强度；模型仍由 .env 的 LLM_MODEL 决定
THINKING_STATE = ThinkingState()
