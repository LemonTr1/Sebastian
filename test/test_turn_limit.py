"""轮次上限收尾测试：最后一轮禁用工具、强制总结、返回部分结果且不抛异常。"""
import sys
import json
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

PASS, FAIL = [], []

def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name} {detail}")


from src.agent_runner import AgentRunner, FINAL_TURN_PROMPT, TURN_LIMIT_FALLBACK
from src.tools.tools_registry import get_tools_registry
from src.tools.toolkits.cron_schedule import CRON_SCHEDULE

CRON_SCHEDULE.agent_lock.acquire()

FAKE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "fake_tool",
        "description": "test tool",
        "parameters": {"type": "object", "properties": {}},
    },
}
FAKE_EXECUTIONS = []

def fake_tool():
    FAKE_EXECUTIONS.append(1)
    return json.dumps({"success": True})

get_tools_registry().register_tool("fake_tool", fake_tool, FAKE_SCHEMA, hitl=False, for_agent="Test_Agent")
get_tools_registry().register_tool("fake_tool", fake_tool, FAKE_SCHEMA, hitl=False, for_agent="Stream_Test_Agent")

USAGE = SimpleNamespace(total_tokens=10)


def make_tc(call_id):
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(name="fake_tool", arguments="{}"),
    )


def make_response(content=None, tool_calls=None):
    msg = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=msg)],
        usage=SimpleNamespace(total_tokens=10),
    )


class FakeClient:
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
        return self.script.pop(0)


def make_chunk(content=None, tool_calls=None, usage=None):
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)], usage=usage)


def usage_only_chunk(usage):
    return SimpleNamespace(choices=[], usage=usage)


def tc_chunk(index, call_id=None, name=None, arguments=None):
    fn = SimpleNamespace(name=name, arguments=arguments)
    return SimpleNamespace(index=index, id=call_id, function=fn)


# ---- run(): 3 轮工具后，第 4 轮（上限）强制收尾 ----
runner = AgentRunner.create_runner("Test_Agent", "test instructions", get_tools_registry())
script = [
    make_response(tool_calls=[make_tc("call_1")]),
    make_response(tool_calls=[make_tc("call_2")]),
    make_response(tool_calls=[make_tc("call_3")]),
    make_response(content="已完成探索；未完成写入，建议下一步继续。"),
]
client = FakeClient(script)
runner.client = client
out = runner.run("do something", max_turns=4)

check("run returns final summary", out == "已完成探索；未完成写入，建议下一步继续。", out[:60])
check("run used exactly max_turns calls", len(client.calls) == 4, str(len(client.calls)))
check("normal turns expose tools", "tools" in client.calls[0] and "tools" in client.calls[2])
check("final turn disables tools", "tools" not in client.calls[-1] and "tool_choice" not in client.calls[-1])
final_msgs = client.calls[-1]["messages"]
check("final turn injects reminder",
      any(m.get("role") == "user" and FINAL_TURN_PROMPT in (m.get("content") or "") for m in final_msgs))
check("run flags hit_turn_limit", runner.hit_turn_limit is True)
check("run clears context after finish", runner.context == [])
check("tools executed during normal turns", len(FAKE_EXECUTIONS) == 3, str(len(FAKE_EXECUTIONS)))

# 收尾轮模型仍返回 tool_calls：不执行，返回兜底总结
runner2 = AgentRunner.create_runner("Test_Agent", "test instructions", get_tools_registry())
runner2.client = FakeClient([
    make_response(tool_calls=[make_tc("call_a")]),
    make_response(tool_calls=[make_tc("call_b")]),
])
FAKE_EXECUTIONS.clear()
out2 = runner2.run("keep calling tools", max_turns=2)
check("final turn ignores tool calls", len(FAKE_EXECUTIONS) == 1, str(len(FAKE_EXECUTIONS)))
check("final turn fallback reply", out2 == TURN_LIMIT_FALLBACK, out2[:60])
check("fallback still flags limit", runner2.hit_turn_limit is True)

# 正常完成不应被标记为触顶
runner3 = AgentRunner.create_runner("Test_Agent", "test instructions", get_tools_registry())
runner3.client = FakeClient([make_response(content="done")])
out3 = runner3.run("simple task", max_turns=5)
check("normal finish returns content", out3 == "done", out3)
check("normal finish not flagged", runner3.hit_turn_limit is False)
check("normal finish one call", len(runner3.client.calls) == 1)


# ---- run_stream(): 上限轮也强制收尾并流式输出 ----
stream_runner = AgentRunner.create_runner("Stream_Test_Agent", "test instructions", get_tools_registry())
stream_script = [
    [
        make_chunk(tool_calls=[tc_chunk(0, None, name="fake_tool", arguments="")]),
        make_chunk(tool_calls=[tc_chunk(0, "call_s1", arguments="{}")]),
        make_chunk(usage=USAGE),
    ],
    [
        make_chunk(content="阶段总结：已完成检索，未完成修改。"),
        make_chunk(usage=USAGE),
    ],
]
stream_client = FakeClient(stream_script)
stream_runner.client = stream_client
tokens = []
FAKE_EXECUTIONS.clear()
stream_runner.run_stream("stream task", on_token=tokens.append, max_turns=2)

check("run_stream final turn disables tools", "tools" not in stream_client.calls[-1])
stream_final_msgs = stream_client.calls[-1]["messages"]
check("run_stream final turn injects reminder",
      any(m.get("role") == "user" and FINAL_TURN_PROMPT in (m.get("content") or "") for m in stream_final_msgs))
check("run_stream streams final summary", "".join(tokens) == "阶段总结：已完成检索，未完成修改。", "".join(tokens))
check("run_stream records last_reply", stream_runner.last_reply == "阶段总结：已完成检索，未完成修改。", stream_runner.last_reply)
check("run_stream flags hit_turn_limit", stream_runner.hit_turn_limit is True)
check("run_stream executed tool once", len(FAKE_EXECUTIONS) == 1, str(len(FAKE_EXECUTIONS)))

# 收尾轮流式返回 tool_calls：不执行，补回 tool 消息保持消息契约
stream_runner2 = AgentRunner.create_runner("Stream_Test_Agent", "test instructions", get_tools_registry())
stream_script2 = [
    [
        make_chunk(tool_calls=[tc_chunk(0, None, name="fake_tool", arguments="")]),
        make_chunk(tool_calls=[tc_chunk(0, "call_s2", arguments="{}")]),
        make_chunk(usage=USAGE),
    ],
    [
        make_chunk(tool_calls=[tc_chunk(0, None, name="fake_tool", arguments="")]),
        make_chunk(tool_calls=[tc_chunk(0, "call_s3", arguments="{}")]),
        make_chunk(usage=USAGE),
    ],
]
stream_client2 = FakeClient(stream_script2)
stream_runner2.client = stream_client2
FAKE_EXECUTIONS.clear()
stream_runner2.run_stream("stream task", on_token=lambda t: None, max_turns=2)

check("run_stream does not execute final-turn tools", len(FAKE_EXECUTIONS) == 1, str(len(FAKE_EXECUTIONS)))
skipped = [m for m in stream_runner2.context if m.get("role") == "tool" and "此工具调用被跳过" in (m.get("content") or "")]
check("run_stream appends skipped tool result", len(skipped) == 1, str(len(skipped)))
check("run_stream fallback last_reply", stream_runner2.last_reply == TURN_LIMIT_FALLBACK, stream_runner2.last_reply)

CRON_SCHEDULE.agent_lock.release()

print(f"\n===== {len(PASS)} passed, {len(FAIL)} failed =====")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
