"""队列线程测试：收件箱有事件即唤醒 Brain；cron 切 Build，后台保持当前模式。"""
import sys
import io
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

PASS, FAIL = [], []

def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name} {detail}")


from cli import _process_queues_once
from src.utils.agent_mode import AGENT_MODE, AgentMode
from src.tools.toolkits.cron_schedule import CRON_SCHEDULE
from src.hooks.hooks_registry import get_hooks_registry
from src.utils.wake_queue import BRAIN_OWNER, WAKE_QUEUE, WakeEvent


class FakeBrain:
    def __init__(self):
        self.inbox_id = BRAIN_OWNER
        self.calls = []
        self.mode_during = None

    def run_stream(self, task, on_token=None):
        self.calls.append(task)
        self.mode_during = AGENT_MODE.get()
        if on_token:
            on_token("x")


def run_once(kinds, events):
    WAKE_QUEUE.clear()
    for kind in kinds:
        WAKE_QUEUE.enqueue(WakeEvent(BRAIN_OWNER, kind, f"{kind} content"))
    brain = FakeBrain()
    hooks = get_hooks_registry()
    buf = io.StringIO()
    with patch.object(hooks, "trigger_hooks", side_effect=lambda event, *a: events.append(event)), \
         patch("cli.ui_redraw.emit_token"), \
         redirect_stdout(buf):
        ok = _process_queues_once(brain)
    return ok, brain, buf.getvalue()


# ---- 1. 纯后台事件：Plan 模式保持 PLAN，仍会唤醒 ----
AGENT_MODE.set(AgentMode.PLAN)
events = []
ok, brain, out = run_once(["background"], events)
check("background-only wakes brain", ok is True and brain.calls == [None], f"{ok} {brain.calls}")
check("background-only keeps plan", brain.mode_during == AgentMode.PLAN and AGENT_MODE.get() == AgentMode.PLAN)
check("background-only triggers stop hook", "Stop" in events, str(events))
check("background-only prints wake reason",
      "background task done, waking Brain" in out, repr(out[:120]))

# ---- 2. cron 事件 + Plan：运行期间切 BUILD，结束后恢复 ----
events = []
ok2, brain2, out2 = run_once(["cron"], events)
check("cron wakes brain", ok2 is True and brain2.calls == [None], f"{ok2} {brain2.calls}")
check("cron switches to build during run", brain2.mode_during == AgentMode.BUILD, str(brain2.mode_during))
check("cron restores plan after run", AGENT_MODE.get() == AgentMode.PLAN)
check("cron triggers stop hook", "Stop" in events, str(events))
check("cron prints scheduled reason", "delivering scheduled starts" in out2, repr(out2[:120]))

# ---- 3. 持锁二次检查为空：不调用模型 ----
WAKE_QUEUE.clear()
brain3 = FakeBrain()
events = []
buf = io.StringIO()
with patch.object(WAKE_QUEUE, "pending_kinds", side_effect=[{"background"}, set()]), \
     patch.object(get_hooks_registry(), "trigger_hooks", side_effect=lambda event, *a: events.append(event)), \
     patch("cli.ui_redraw.emit_token"), \
     redirect_stdout(buf):
    ok3 = _process_queues_once(brain3)
out3 = buf.getvalue()
check("second check empty returns false", ok3 is False)
check("second check empty no model call", brain3.calls == [])
check("second check empty no stop hook", "Stop" not in events, str(events))
check("second check empty no wake line", "[queue processor]" not in out3, repr(out3[:120]))

# ---- 4. agent_lock 被占用：不等待、不调用 ----
WAKE_QUEUE.clear()
WAKE_QUEUE.enqueue(WakeEvent(BRAIN_OWNER, "background", "content"))
brain4 = FakeBrain()
buf = io.StringIO()
CRON_SCHEDULE.agent_lock.acquire()
try:
    with patch("cli.ui_redraw.emit_token"), redirect_stdout(buf):
        ok4 = _process_queues_once(brain4)
finally:
    CRON_SCHEDULE.agent_lock.release()
out4 = buf.getvalue()
check("locked returns false", ok4 is False)
check("locked no model call", brain4.calls == [])
check("locked no wake line", "[queue processor]" not in out4, repr(out4[:120]))

# ---- 5. 空收件箱：不调用模型 ----
WAKE_QUEUE.clear()
brain5 = FakeBrain()
buf = io.StringIO()
with patch("cli.ui_redraw.emit_token"), redirect_stdout(buf):
    ok5 = _process_queues_once(brain5)
check("empty inbox returns false", ok5 is False)
check("empty inbox no model call", brain5.calls == [])

WAKE_QUEUE.clear()
AGENT_MODE.set(AgentMode.BUILD)

print(f"\n===== {len(PASS)} passed, {len(FAIL)} failed =====")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
