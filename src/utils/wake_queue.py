"""统一唤醒收件箱：cron 与后台任务共用同一套生产/消费模型。

生产者（cron 调度线程、后台任务 worker）投递 WakeEvent；
消费者（AgentRunner 的每次运行）按 owner 原子取走并注入上下文；
队列线程只检查是否有待处理事件，用它决定是否唤醒 Brain。
"""
from collections import deque
from dataclasses import dataclass
import threading

BRAIN_OWNER = "Brain_Agent"


@dataclass(frozen=True)
class WakeEvent:
    owner: str
    kind: str       # "cron" / "background"
    content: str    # 直接注入上下文的 user 消息


class WakeQueue:
    def __init__(self):
        self._events: deque[WakeEvent] = deque()
        self._lock = threading.Lock()

    def enqueue(self, event: WakeEvent) -> None:
        with self._lock:
            self._events.append(event)

    def drain(self, owner: str) -> list[WakeEvent]:
        """原子取走某个 owner 的全部事件，保持到达顺序"""
        with self._lock:
            kept, drained = deque(), []
            for event in self._events:
                (drained if event.owner == owner else kept).append(event)
            self._events = kept
        return drained

    def pending_kinds(self, owner: str) -> set[str]:
        with self._lock:
            return {e.kind for e in self._events if e.owner == owner}

    def has_pending(self, owner: str, kind: str | None = None) -> bool:
        with self._lock:
            return any(
                e.owner == owner and (kind is None or e.kind == kind)
                for e in self._events
            )

    def drop_owner(self, owner: str) -> None:
        """丢弃某个 owner 的事件（子 Agent 结束后清掉无人消费的遗留）"""
        with self._lock:
            self._events = deque(e for e in self._events if e.owner != owner)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


WAKE_QUEUE = WakeQueue()
