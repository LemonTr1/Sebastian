"""Plan/Build 模式端到端流式集成测试（fake client，不触发真实 API）。

场景1（Plan）：模型试图调用 bash → schema 中无 bash → 运行时被拒并回填错误结果
场景2（Build）：全部工具 schema + ls 正常执行
"""
import sys
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

PASS, FAIL = [], []

def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name} {detail}")


from src.utils.agent_mode import AGENT_MODE, AgentMode
from src.tools.tools_registry import get_tools_registry
from src.agent_runner import AgentRunner
from src.tools.toolkits.cron_schedule import CRON_SCHEDULE

CRON_SCHEDULE.agent_lock.acquire()

ALLOWED = ["read", "glob", "grep", "ls", "todo", "web_search", "web_fetch", "load_skill", "list_crons"]
FORBIDDEN = ["bash", "write", "edit", "agent", "schedule_cron", "cancel_cron"]

USAGE = SimpleNamespace(total_tokens=10)


def make_chunk(content=None, tool_calls=None, usage=None):
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)], usage=usage)


def usage_only_chunk(usage):
    """OpenAI 规范：include_usage 时追加的终止块，choices 为空，仅带 usage"""
    return SimpleNamespace(choices=[], usage=usage)


def tc_chunk(index, call_id=None, name=None, arguments=None):
    fn = SimpleNamespace(name=name, arguments=arguments)
    return SimpleNamespace(index=index, id=call_id, function=fn)


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


# ---- 场景1：Plan 模式 ----
AGENT_MODE.set(AgentMode.PLAN)
runner = AgentRunner.create_runner("Brain_Agent", "base instructions", get_tools_registry())
script = [
    # 第1轮：模型试图调用 bash
    [
        make_chunk(tool_calls=[tc_chunk(0, None, name="bash", arguments="")]),
        make_chunk(tool_calls=[tc_chunk(0, "call_1", arguments='{"command": "ls", "description": "list"}')]),
        make_chunk(usage=USAGE),
    ],
    # 第2轮：收到拒绝结果，输出计划并询问用户
    [
        make_chunk(content="计划如下：清理临时文件。是否立即执行？"),
        make_chunk(usage=USAGE),
    ],
]
client = FakeStreamClient(script)
runner.client = client
with patch.object(CRON_SCHEDULE, "consume_cron_queue", return_value=[]):
    runner.run_stream("请规划一个清理临时文件的任务", on_token=lambda t: None)

first_tools = [s["function"]["name"] for s in client.calls[0]["tools"]]
check("plan schema only 9 tools", sorted(first_tools) == sorted(ALLOWED), str(sorted(first_tools)))
check("plan schema excludes bash", "bash" not in first_tools)
check("plan schema excludes all forbidden", not (set(first_tools) & set(FORBIDDEN)))

rejected = [m for m in runner.context if m.get("role") == "tool" and "Plan 模式下不可用" in m.get("content", "")]
check("bash rejected at runtime", len(rejected) == 1, str(len(rejected)))

second_messages = client.calls[1]["messages"]
has_reject = any(m.get("role") == "tool" and "Plan 模式下不可用" in m.get("content", "") for m in second_messages)
check("rejection fed back to llm", has_reject)
check("planning answer returned", any(m.get("role") == "assistant" and "计划如下" in m.get("content", "") for m in runner.context))

# ---- 场景2：Build 模式 ----
AGENT_MODE.set(AgentMode.BUILD)
runner2 = AgentRunner.create_runner("Brain_Agent", "base instructions", get_tools_registry())
script2 = [
    [
        make_chunk(tool_calls=[tc_chunk(0, None, name="ls", arguments="")]),
        make_chunk(tool_calls=[tc_chunk(0, "call_2", arguments=json.dumps({"path": str(Path.home())}))]),
        make_chunk(usage=USAGE),
    ],
    [
        make_chunk(content="已列出家目录"),
        make_chunk(usage=USAGE),
    ],
]
client2 = FakeStreamClient(script2)
runner2.client = client2
with patch.object(CRON_SCHEDULE, "consume_cron_queue", return_value=[]):
    runner2.run_stream("列出家目录", on_token=lambda t: None)

first_tools2 = [s["function"]["name"] for s in client2.calls[0]["tools"]]
check("build schema full 15 tools", sorted(first_tools2) == sorted(ALLOWED + FORBIDDEN), str(len(first_tools2)))
check("build schema has bash", "bash" in first_tools2)

ls_msgs = [m for m in runner2.context if m.get("role") == "tool" and m.get("tool_call_id") == "call_2"]
check("ls executed in build", len(ls_msgs) == 1 and "success" in ls_msgs[0]["content"])

# ---- 场景3：usage-only 终止块（空 choices）不应导致崩溃 ----
from src.utils.tokens_caculator import get_total_session_tokens
get_total_session_tokens().clear()
runner3 = AgentRunner.create_runner("Brain_Agent", "base instructions", get_tools_registry())
script3 = [
    [
        make_chunk(content="你好，我是 Sebastian"),
        usage_only_chunk(USAGE),
    ],
]
client3 = FakeStreamClient(script3)
runner3.client = client3
err3 = None
with patch.object(CRON_SCHEDULE, "consume_cron_queue", return_value=[]):
    try:
        runner3.run_stream("你好", on_token=lambda t: None)
    except Exception as e:
        err3 = e
check("usage-only chunk no crash", err3 is None, repr(err3))
check("usage-only chunk content kept",
      any(m.get("role") == "assistant" and m.get("content") == "你好，我是 Sebastian" for m in runner3.context))
check("usage-only chunk usage counted",
      get_total_session_tokens().accumulate_token() == 10, str(get_total_session_tokens().accumulate_token()))

empty_msg = runner3._extract_assistant_msg(SimpleNamespace(choices=[]))
check("extract_assistant_msg empty choices safe",
      empty_msg.get("role") == "assistant" and empty_msg.get("content") is None)

AGENT_MODE.set(AgentMode.BUILD)
CRON_SCHEDULE.agent_lock.release()

print(f"\n===== {len(PASS)} passed, {len(FAIL)} failed =====")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
