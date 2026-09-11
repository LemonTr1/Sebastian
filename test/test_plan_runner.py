"""Plan 模式在 AgentRunner 层的限制测试：
工具表过滤、system 提示词注入、禁用工具拒绝（先于钩子）、Build 恢复、白名单工具正常执行"""
import sys
import json
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

PASS, FAIL = [], []

def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name} {detail}")


from src.utils.agent_mode import AGENT_MODE, AgentMode
from src.tools.tools_registry import get_tools_registry
from src.agent_runner import AgentRunner
from src.hooks.hooks_registry import get_hooks_registry
from src.tools.toolkits.cron_schedule import CRON_SCHEDULE

CRON_SCHEDULE.agent_lock.acquire()

ALLOWED = {"read", "glob", "grep", "ls", "todo", "web_search", "web_fetch", "load_skill", "list_crons"}
FORBIDDEN = {"bash", "write", "edit", "agent", "schedule_cron", "cancel_cron"}

AGENT_MODE.set(AgentMode.BUILD)
runner = AgentRunner.create_runner("Brain_Agent", "base instructions", get_tools_registry())

full_keys = set(runner.tool_map.keys())
check("build full tools (15)", full_keys == ALLOWED | FORBIDDEN, str(full_keys))
check("build active == full", set(runner._active_tool_map().keys()) == full_keys)

# ---- 进入 Plan 模式 ----
AGENT_MODE.set(AgentMode.PLAN)
active = runner._active_tool_map()
check("plan active only 9", set(active.keys()) == ALLOWED, str(set(active.keys())))

# system 提示词注入
runner.context = []
runner._ensure_system_prompt()
sys_content = runner.context[0]["content"]
check("plan section injected", "当前模式：Plan" in sys_content)
check("plan lists forbidden", "【禁止工具】" in sys_content and "bash" in sys_content)
check("plan guides /build", "/build" in sys_content)

# 禁用工具调用：必须在 PreToolUse 钩子之前被拒绝（不弹 HITL）
runner.context = []
runner._ensure_system_prompt()
tc = {"id": "call_x", "type": "function", "function": {"name": "bash", "arguments": '{"command": "ls", "description": "list"}'}}
hook_events = []
registry = get_hooks_registry()
orig_trigger = registry.trigger_hooks

def spy_trigger(event, *args):
    hook_events.append(event)
    return orig_trigger(event, *args)

with patch.object(registry, "trigger_hooks", side_effect=spy_trigger):
    runner._process_tool_calls([tc], runner._active_tool_map())

tool_msgs = [m for m in runner.context if m.get("role") == "tool" and m.get("tool_call_id") == "call_x"]
check("forbidden tool rejected", len(tool_msgs) == 1 and "Plan 模式下不可用" in tool_msgs[0]["content"], tool_msgs[0]["content"][:80] if tool_msgs else "none")
check("rejected before hooks", "PreToolUse" not in hook_events, str(hook_events))

# 白名单工具在 Plan 下正常执行（ls 非 HITL）
tc2 = {"id": "call_y", "type": "function", "function": {"name": "ls", "arguments": json.dumps({"path": str(Path.home())})}}
runner._process_tool_calls([tc2], runner._active_tool_map())
ls_msgs = [m for m in runner.context if m.get("role") == "tool" and m.get("tool_call_id") == "call_y"]
check("allowed tool executes in plan", len(ls_msgs) == 1 and "success" in ls_msgs[0]["content"])

# ---- 退出 Plan 模式 ----
AGENT_MODE.set(AgentMode.BUILD)
check("build active restored", set(runner._active_tool_map().keys()) == full_keys)
runner.context = []
runner._ensure_system_prompt()
check("plan section removed", "当前模式：Plan" not in runner.context[0]["content"])

CRON_SCHEDULE.agent_lock.release()

print(f"\n===== {len(PASS)} passed, {len(FAIL)} failed =====")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
