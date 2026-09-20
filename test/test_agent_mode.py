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
with mock.patch.object(hitl_mod._approval_client, "ask", return_value=False) as ask_mock:
    result = hitl_mod.hitl_hook("Brain_Agent", tool_call)
check("auto mode skips approval", result is None and not ask_mock.called)

AGENT_MODE.set(AgentMode.BUILD)
with mock.patch.object(hitl_mod._approval_client, "ask", return_value=True) as ask_mock:
    result = hitl_mod.hitl_hook("Brain_Agent", tool_call)
check("build mode asks approval", result is None and ask_mock.called)

# 全局单例复位
AGENT_MODE.set(AgentMode.BUILD)
check("global singleton reset", not AGENT_MODE.is_plan() and not AGENT_MODE.is_auto())

CRON_SCHEDULE.agent_lock.release()

print(f"\n===== {len(PASS)} passed, {len(FAIL)} failed =====")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
