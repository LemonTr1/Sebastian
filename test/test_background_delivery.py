"""统一收件箱投递测试：运行开头注入、按 owner 隔离、不重复、空唤醒不调模型。"""
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

PASS, FAIL = [], []

def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name} {detail}")


from src.agent_runner import AgentRunner
from src.tools.tools_registry import get_tools_registry
from src.utils.wake_queue import WAKE_QUEUE, WakeEvent

USAGE = SimpleNamespace(total_tokens=10)


def make_chunk(content=None, tool_calls=None, usage=None):
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)], usage=usage)


def usage_only_chunk(usage):
    return SimpleNamespace(choices=[], usage=usage)


class FakeStreamClient:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return iter(self.script.pop(0))


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def make_response(content):
    msg = SimpleNamespace(content=content, tool_calls=None)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=msg)],
        usage=SimpleNamespace(total_tokens=10),
    )


def user_text(kwargs):
    return "\n".join(
        m.get("content") or ""
        for m in kwargs["messages"]
        if m.get("role") == "user"
    )


def enqueue(runner, kind="background", content="<task_notification><task_id>bg1</task_id></task_notification>"):
    WAKE_QUEUE.enqueue(WakeEvent(owner=runner.inbox_id, kind=kind, content=content))


# ---- 1. run_stream 开头注入，且只注入一次 ----
WAKE_QUEUE.clear()
runner = AgentRunner.create_runner("Test_Agent", "instructions", get_tools_registry())
runner.client = FakeStreamClient([
    [make_chunk(content="已处理事件"), usage_only_chunk(USAGE)],
    [make_chunk(content="第二轮"), usage_only_chunk(USAGE)],
])
enqueue(runner)
runner.run_stream("hi", on_token=lambda t: None)
runner.run_stream("again", on_token=lambda t: None)

check("stream first call injects event", "<task_id>bg1</task_id>" in user_text(runner.client.calls[0]))
check("stream reply kept", runner.last_reply == "第二轮", runner.last_reply)
check("event drained after stream", not WAKE_QUEUE.has_pending(runner.inbox_id))
count = sum(
    1
    for m in runner.context
    if m.get("role") == "user" and "<task_id>bg1</task_id>" in (m.get("content") or "")
)
check("event not duplicated", count == 1, str(count))

# ---- 2. run_stream(None)：有事件会唤醒模型 ----
WAKE_QUEUE.clear()
wake = AgentRunner.create_runner("Wake_Agent", "instructions", get_tools_registry())
wake.client = FakeStreamClient([[make_chunk(content="后台完成，已汇报"), usage_only_chunk(USAGE)]])
enqueue(wake, content="<task_id>bg_wake</task_id>")
wake.run_stream(None, on_token=lambda t: None)
check("run_stream(None) wakes for event", len(wake.client.calls) == 1, str(len(wake.client.calls)))
check("run_stream(None) injected event", "<task_id>bg_wake</task_id>" in user_text(wake.client.calls[0]))

# ---- 3. run_stream(None)：空收件箱直接返回 ----
WAKE_QUEUE.clear()
idle = AgentRunner.create_runner("Idle_Agent", "instructions", get_tools_registry())
idle.client = FakeStreamClient([])
idle.run_stream(None, on_token=lambda t: None)
check("empty wake makes no model call", idle.client.calls == [], str(idle.client.calls))
check("empty wake leaves only system context",
      [m.get("role") for m in idle.context] == ["system"], str([m.get("role") for m in idle.context]))

# ---- 4. run() 子 Agent 路径同样注入，结束后关闭收件箱 ----
WAKE_QUEUE.clear()
sub = AgentRunner.create_runner("Run_Agent", "instructions", get_tools_registry())
sub.client = FakeClient([make_response("done")])
enqueue(sub, content="<task_id>bg_run</task_id>")
out = sub.run("task")
check("run injects event", "<task_id>bg_run</task_id>" in user_text(sub.client.calls[0]))
check("run returns reply", out == "done", out)
check("run clears context", sub.context == [])
check("run closes inbox", sub._closed is True)
check("run leaves no pending events", not WAKE_QUEUE.has_pending(sub.inbox_id))

# ---- 5. owner 隔离：别的 Agent 的事件不会被取走 ----
WAKE_QUEUE.clear()
iso = AgentRunner.create_runner("Iso_Agent", "instructions", get_tools_registry())
iso.client = FakeStreamClient([[make_chunk(content="ok"), usage_only_chunk(USAGE)]])
WAKE_QUEUE.enqueue(WakeEvent(owner="Other_Agent", kind="background", content="other"))
enqueue(iso, content="<task_id>bg_iso</task_id>")
iso.run_stream("hi", on_token=lambda t: None)
check("owner event injected", "<task_id>bg_iso</task_id>" in user_text(iso.client.calls[0]))
check("other owner event untouched", WAKE_QUEUE.has_pending("Other_Agent"), str(WAKE_QUEUE.pending_kinds("Other_Agent")))

# ---- 6. 并发 drain：每条事件只被一个线程取走 ----
WAKE_QUEUE.clear()
for i in range(30):
    WAKE_QUEUE.enqueue(WakeEvent(owner="conc", kind="background", content=f"out_{i}"))
results, errors = [], []
lock = threading.Lock()


def drain_worker():
    try:
        events = WAKE_QUEUE.drain("conc")
        with lock:
            results.extend(events)
    except Exception as e:
        with lock:
            errors.append(e)


threads = [threading.Thread(target=drain_worker) for _ in range(2)]
for t in threads:
    t.start()
for t in threads:
    t.join(timeout=5)

ids = {e.content for e in results}
check("concurrent drain no errors", errors == [], repr(errors))
check("concurrent drain total 30", len(results) == 30, str(len(results)))
check("concurrent drain no duplicates", len(ids) == 30, str(len(ids)))
check("concurrent drain empty after", not WAKE_QUEUE.has_pending("conc"))

# ---- 7. 后台 worker 生产事件：格式化、状态清理、投递 ----
WAKE_QUEUE.clear()
BG_DONE = threading.Event()


def bg_tool():
    BG_DONE.set()
    return "bg-output"


bg_runner = AgentRunner.create_runner("Bg_Producer_Agent", "instructions", get_tools_registry())
bg_id = bg_runner.start_background_task("call_bg", "bg_tool", {}, {"bg_tool": {"func": bg_tool}})
BG_DONE.wait(timeout=2)
deadline = time.monotonic() + 2
while time.monotonic() < deadline and not WAKE_QUEUE.has_pending(bg_runner.inbox_id, "background"):
    time.sleep(0.01)
events = WAKE_QUEUE.drain(bg_runner.inbox_id)
check("worker enqueues one event", len(events) == 1, str(len(events)))
check("worker event kind", bool(events) and events[0].kind == "background", events[0].kind if events else "")
check("worker event content", "<task_notification>" in (events[0].content if events else "")
      and "bg-output" in (events[0].content if events else ""))
check("worker clears running status", bg_id not in bg_runner.background_tasks)

# ---- 8. 已关闭的子 Agent 不再投递事件 ----
WAKE_QUEUE.clear()
closed = AgentRunner.create_runner("Closed_Agent", "instructions", get_tools_registry())
closed.client = FakeClient([make_response("done")])
closed.run("task")  # 结束时 _closed=True
BG_DONE.clear()
closed_bg = closed.start_background_task("call_after", "bg_tool", {}, {"bg_tool": {"func": bg_tool}})
BG_DONE.wait(timeout=2)
deadline = time.monotonic() + 2
while time.monotonic() < deadline and closed_bg in closed.background_tasks:
    time.sleep(0.01)
check("closed agent drops event", not WAKE_QUEUE.has_pending(closed.inbox_id))

WAKE_QUEUE.clear()

print(f"\n===== {len(PASS)} passed, {len(FAIL)} failed =====")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
