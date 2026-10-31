"""终端噪音测试：子 Agent 的工具调用与后台任务日志不打印，Brain 仍照常打印。"""
import sys
import io
import json
import threading
import time
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

PASS, FAIL = [], []

def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name} {detail}")


from src.agent_runner import AgentRunner
from src.tools.tools_registry import get_tools_registry
from src.utils.wake_queue import WAKE_QUEUE

SCHEMA = {
    "type": "function",
    "function": {
        "name": "silent_tool",
        "description": "test tool",
        "parameters": {"type": "object", "properties": {}},
    },
}

BG_EVENT = threading.Event()

def silent_tool():
    return json.dumps({"success": True})

def silent_bg_tool():
    BG_EVENT.set()
    return json.dumps({"success": True})

get_tools_registry().register_tool("silent_tool", silent_tool, SCHEMA, hitl=False, for_agent="Quiet_Agent")
get_tools_registry().register_tool("silent_tool", silent_tool, SCHEMA, hitl=False, for_agent="Brain_Agent")

TC = {"id": "call_silent", "type": "function", "function": {"name": "silent_tool", "arguments": "{}"}}


def wait_completed(runner, bg_id, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with runner.background_lock:
            if bg_id not in runner.background_tasks:
                return
        time.sleep(0.01)


WAKE_QUEUE.clear()
sub = AgentRunner.create_runner("Quiet_Agent", "test", get_tools_registry())
buf = io.StringIO()
with redirect_stdout(buf):
    sub._process_tool_calls([TC], sub.tool_map)
out = buf.getvalue()
check("subagent tool call silent", "[TOOL]" not in out, repr(out[:120]))

brain = AgentRunner.create_runner("Brain_Agent", "test", get_tools_registry())
buf2 = io.StringIO()
with redirect_stdout(buf2):
    brain._process_tool_calls([TC], brain.tool_map)
out2 = buf2.getvalue()
check("brain tool call printed", "[TOOL] Brain_Agent 调用 silent_tool" in out2, repr(out2[:120]))

# 后台任务日志：子 Agent 静默，Brain 可见
bg_map = {"silent_tool": {"func": silent_bg_tool}}
buf3 = io.StringIO()
with redirect_stdout(buf3):
    bg_id = sub.start_background_task("call_bg", "silent_tool", {}, bg_map)
    BG_EVENT.wait(timeout=2)
    wait_completed(sub, bg_id)
sub_events = WAKE_QUEUE.drain(sub.inbox_id)
out3 = buf3.getvalue()
check("subagent background silent", "[background" not in out3, repr(out3[:120]))
check("subagent background status cleared", bg_id not in sub.background_tasks, str(sub.background_tasks))
check("subagent background event queued", len(sub_events) == 1, str(len(sub_events)))

BG_EVENT.clear()
buf4 = io.StringIO()
with redirect_stdout(buf4):
    bg_id2 = brain.start_background_task("call_bg2", "silent_tool", {}, bg_map)
    BG_EVENT.wait(timeout=2)
    wait_completed(brain, bg_id2)
brain_events = WAKE_QUEUE.drain(brain.inbox_id)
out4 = buf4.getvalue()
check("brain background printed", "[background] 后台任务启动" in out4 and "[background done]" in out4, repr(out4[:160]))
check("brain background event queued", len(brain_events) == 1, str(len(brain_events)))

WAKE_QUEUE.clear()
print(f"\n===== {len(PASS)} passed, {len(FAIL)} failed =====")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
