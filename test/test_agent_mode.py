"""AgentMode 单元测试：模式状态（Build/Plan/Auto）、白名单、禁用集推导、提示词生成、Auto 免审批"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

PASS, FAIL = [], []

def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name} {detail}")


from src.utils.agent_mode import AgentMode, AGENT_MODE
from src.tools.toolkits.cron_schedule import CRON_SCHEDULE

# 阻止定时任务在测试期间触发真实 API 调用
CRON_SCHEDULE.agent_lock.acquire()

m = AgentMode()
check("default build", m.get() == AgentMode.BUILD)
check("not plan by default", not m.is_plan())

m.set(AgentMode.PLAN)
check("set plan", m.is_plan() and m.get() == AgentMode.PLAN)
m.set(AgentMode.BUILD)
check("set build", not m.is_plan() and not m.is_auto())
check("not auto by default", not AgentMode().is_auto())

m.set(AgentMode.AUTO)
check("set auto", m.is_auto() and m.get() == AgentMode.AUTO and not m.is_plan())
m.set(AgentMode.BUILD)
check("leave auto", not m.is_auto())

ALLOWED = {"read", "glob", "grep", "ls", "todo", "web_search", "web_fetch", "load_skill", "list_crons", "question"}
check("allowed 10 tools", m.allowed_tools() == frozenset(ALLOWED))

ALL_TOOLS = ALLOWED | {"bash", "write", "edit", "agent", "schedule_cron", "cancel_cron"}
forbidden = m.forbidden_tools(ALL_TOOLS)
check("forbidden set derived", set(forbidden) == {"agent", "bash", "cancel_cron", "edit", "schedule_cron", "write"}, str(forbidden))

desc = m.describe(ALL_TOOLS)
check("describe mode title", "当前模式：Plan" in desc)
check("describe allowed list", "【可用工具】" in desc and "read" in desc)
check("describe forbidden list", "【禁止工具】" in desc and "bash" in desc)
check("describe planning focus", "以思考与规划为主" in desc)
check("describe ask user", "询问用户" in desc and "/build" in desc)

# ---- Auto 模式下 HITL 钩子免审批 ----
import importlib
from unittest import mock

hitl_mod = importlib.import_module("src.hooks.pre_tool_use.02_hitl_hook")

tool_call = {"function": {"name": "bash", "arguments": '{"command": "ls"}'}}

AGENT_MODE.set(AgentMode.AUTO)
with mock.patch.object(hitl_mod, "terminal_confirm", return_value=False) as ask_mock:
    result = hitl_mod.hitl_hook("Brain_Agent", tool_call)
check("auto mode skips approval", result is None and not ask_mock.called)

AGENT_MODE.set(AgentMode.BUILD)
with mock.patch.object(hitl_mod, "terminal_confirm", return_value=True) as ask_mock:
    result = hitl_mod.hitl_hook("Brain_Agent", tool_call)
check("build mode asks approval", result is None and ask_mock.called)

# ---- 子 Agent 内部工具不走 HITL，安全边界在 agent 调度 ----
from src.tools.tools_registry import get_tools_registry as _get_registry
_reg = _get_registry()
if "bash" in _reg.tools_map:
    _reg.register_tool("bash", _reg.tools_map["bash"][0], _reg.tools_map["bash"][1], hitl=False, for_agent="TestRunner")
with mock.patch.object(hitl_mod, "terminal_confirm", return_value=False) as ask_mock:
    result = hitl_mod.hitl_hook("TestRunner", tool_call)
check("subagent tool bypasses HITL", result is None and not ask_mock.called)

# 全局单例复位
AGENT_MODE.set(AgentMode.BUILD)
check("global singleton reset", not AGENT_MODE.is_plan() and not AGENT_MODE.is_auto())

# ---- tool 消息顺序：被拦截/跳过也必须按 tool_calls 声明顺序回填 ----
import json
import threading
from src.agent_runner import AgentRunner

runner = object.__new__(AgentRunner)
runner.name = "Brain_Agent"
runner.model = "deepseek-v4-flash"
runner.context = []
runner.tool_map = {"noop": {"func": lambda **kw: "ok", "schema": {}}}
runner.pre_tool_use_lock = threading.Lock()
runner.background_lock = threading.Lock()
runner.background_tasks = {}

tool_calls = [
    {"id": "call_1", "type": "function", "function": {"name": "noop", "arguments": "{}"}},
    {"id": "call_2", "type": "function", "function": {"name": "noop", "arguments": "{}"}},
    {"id": "call_3", "type": "function", "function": {"name": "noop", "arguments": "{}"}},
]

seen = {"n": 0}
def _fake_trigger(event, agent_name, tc):
    seen["n"] += 1
    if seen["n"] == 2:
        return json.dumps({"error": "blocked"}, ensure_ascii=False)
    return None

fake_registry = mock.Mock()
fake_registry.trigger_hooks.side_effect = _fake_trigger
with mock.patch("src.agent_runner.get_hooks_registry", return_value=fake_registry):
    runner._process_tool_calls(tool_calls)

ids = [msg.get("tool_call_id") for msg in runner.context if msg.get("role") == "tool"]
check("tool messages keep declared order", ids == ["call_1", "call_2", "call_3"], str(ids))
check("first tool result is execution result", runner.context[0]["content"] == "ok")
check("second tool result is hook block", "blocked" in runner.context[1]["content"])
check("third tool result is skip", "已被跳过" in runner.context[2]["content"])

CRON_SCHEDULE.agent_lock.release()

print(f"\n===== {len(PASS)} passed, {len(FAIL)} failed =====")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
