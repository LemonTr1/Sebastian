"""思考参数与 reasoning_content 回传测试。"""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

PASS, FAIL = [], []

def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name} {detail}")


import src.agent_runner as ar
from src.agent_runner import AgentRunner
from src.tools.tools_registry import get_tools_registry

ar.PROVIDER = "deepseek"
ar.THINKING_STATE.set("medium")


def make_response(content=None, tool_calls=None, reasoning_content=None):
    msg = SimpleNamespace(content=content, tool_calls=tool_calls, reasoning_content=reasoning_content)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=msg)],
        usage=SimpleNamespace(total_tokens=10),
    )


def make_chunk(content=None, reasoning_content=None):
    delta = SimpleNamespace(content=content, tool_calls=None, reasoning_content=reasoning_content)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)], usage=None)


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
        snapshot = dict(kwargs)
        if "messages" in snapshot:
            snapshot["messages"] = [dict(m) for m in snapshot["messages"]]
        self.calls.append(snapshot)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


# ---- 非流式：保留 reasoning_content ----
runner = AgentRunner.create_runner("Reasoning_Test_Agent", "test instructions", get_tools_registry())
extracted = runner._extract_assistant_msg(
    make_response(content="answer", reasoning_content="think")
)
check("non-stream keeps reasoning", extracted.get("reasoning_content") == "think", str(extracted))
check("non-stream keeps content", extracted.get("content") == "answer", str(extracted))

# ---- 流式：收集 reasoning，但不喂给 on_token ----
runner_stream = AgentRunner.create_runner("Reasoning_Stream_Agent", "test instructions", get_tools_registry())
runner_stream.client = FakeClient([[make_chunk(reasoning_content="think"), make_chunk(content="answer")]])
tokens = []
runner_stream.run_stream("hi", on_token=tokens.append)
assistant = runner_stream.context[-1]
check("stream keeps reasoning", assistant.get("reasoning_content") == "think", str(assistant))
check("stream keeps content", assistant.get("content") == "answer", str(assistant))
check("stream hides reasoning from tokens", tokens == ["answer"], str(tokens))

# ---- 400：剥离思考参数与历史 reasoning_content 后重试 ----
runner_retry = AgentRunner.create_runner("Reasoning_Retry_Agent", "test instructions", get_tools_registry())
runner_retry.context = [
    {"role": "system", "content": "sys"},
    {"role": "assistant", "content": "old", "reasoning_content": "old-think"},
    {"role": "user", "content": "prev"},
]
client = FakeClient([Exception("thinking is not supported"), make_response(content="ok")])
runner_retry.client = client
result = runner_retry.run("go")

check("retry returns content", result == "ok", result)
check("first call carries thinking params",
      "reasoning_effort" in client.calls[0] or "extra_body" in client.calls[0],
      str(client.calls[0].keys()))
check("retry strips thinking params",
      "reasoning_effort" not in client.calls[1] and "extra_body" not in client.calls[1],
      str(client.calls[1].keys()))
check("retry strips historical reasoning",
      all("reasoning_content" not in m for m in client.calls[1].get("messages", [])),
      str(client.calls[1].get("messages", [])))

print(f"\n===== {len(PASS)} passed, {len(FAIL)} failed =====")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
