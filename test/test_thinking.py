"""思考强度映射与会话状态测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

PASS, FAIL = [], []

def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name} {detail}")


from src.utils.thinking import (
    build_thinking_kwargs,
    detect_provider,
    is_forced_thinking,
    thinking_options,
)
from src.utils.thinking_state import ThinkingState

# ---- 厂商识别 ----
URLS = {
    "https://api.deepseek.com": "deepseek",
    "https://dashscope.aliyuncs.com/compatible-mode/v1": "qwen",
    "https://open.bigmodel.cn/api/paas/v4": "glm",
    "https://api.moonshot.cn/v1": "kimi",
    "https://api.x.ai/v1": "grok",
    "https://api.openai.com/v1": "openai",
    "https://api.anthropic.com/v1/": "claude",
    "https://generativelanguage.googleapis.com/v1beta/openai/": "gemini",
}
for url, expected in URLS.items():
    check(f"detect {expected}", detect_provider(url) == expected, str(detect_provider(url)))
check("unknown provider", detect_provider("https://gateway.local/v1") is None)
check("empty provider", detect_provider("") is None)

# ---- 强制思考 ----
check("grok forced", is_forced_thinking("grok-4.7"))
check("glm-5.3 forced", is_forced_thinking("glm-5.3-flash"))
check("deepseek not forced", not is_forced_thinking("deepseek-flash"))
check("gpt-6.1-sol forced", is_forced_thinking("gpt-6.1-sol"))

options = thinking_options("grok", "grok-4.7")
check("grok off unavailable", options[0]["available"] is False and options[0]["note"])
check("grok medium available", options[1]["available"] is True)
options = thinking_options("deepseek", "deepseek-flash")
check("deepseek off available", options[0]["available"] is True)
options = thinking_options("gemini", "gemini-2.5-flash")
check("gemini off unavailable", options[0]["available"] is False)
options = thinking_options("kimi", "kimi-k2.6")
check("kimi k2.6 off available", options[0]["available"] is True)

# ---- 参数映射 ----
check(
    "deepseek medium",
    build_thinking_kwargs("deepseek", "deepseek-flash", "medium")
    == {"reasoning_effort": "high", "extra_body": {"thinking": {"type": "enabled"}}},
)
check(
    "deepseek off",
    build_thinking_kwargs("deepseek", "deepseek-flash", "off")
    == {"extra_body": {"thinking": {"type": "disabled"}}},
)
check(
    "qwen max",
    build_thinking_kwargs("qwen", "qwen3.8-max", "max")
    == {"extra_body": {"enable_thinking": True, "reasoning_effort": "xhigh"}},
)
check(
    "glm forced off ignored",
    build_thinking_kwargs("glm", "glm-5.3", "off") == {},
)
check(
    "glm medium",
    build_thinking_kwargs("glm", "glm-5.3", "medium")
    == {"extra_body": {"thinking": {"type": "enabled"}}, "reasoning_effort": "high"},
)
check(
    "kimi k3 medium",
    build_thinking_kwargs("kimi", "kimi-k3", "medium") == {"reasoning_effort": "high"},
)
check(
    "kimi k2.6 off",
    build_thinking_kwargs("kimi", "kimi-k2.6", "off")
    == {"extra_body": {"thinking": {"type": "disabled"}}},
)
check(
    "grok max",
    build_thinking_kwargs("grok", "grok-4.7", "max") == {"reasoning_effort": "xhigh"},
)
check(
    "openai off",
    build_thinking_kwargs("openai", "gpt-6-sol", "off") == {"reasoning_effort": "none"},
)
check(
    "openai forced off ignored",
    build_thinking_kwargs("openai", "gpt-6-astra", "off") == {},
)
check(
    "claude medium",
    build_thinking_kwargs("claude", "claude-haiku-5-5", "medium")
    == {
        "extra_body": {
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": "medium"},
        }
    },
)
check(
    "gemini max",
    build_thinking_kwargs("gemini", "gemini-4-argon", "max")
    == {"reasoning_effort": "high"},
)
check("gemini off unsupported", build_thinking_kwargs("gemini", "gemini-2.5-flash", "off") == {})
check(
    "claude forced off ignored",
    build_thinking_kwargs("claude", "claude-sonnet-5-5", "off") == {},
)
check("unknown provider kwargs", build_thinking_kwargs(None, "x", "medium") == {})

try:
    build_thinking_kwargs("deepseek", "deepseek-flash", "bad")
    check("invalid level raises", False)
except ValueError:
    check("invalid level raises", True)

# ---- 状态 ----
state = ThinkingState()
check("state default medium", state.snapshot() == "medium")
state.set("max")
check("state set max", state.snapshot() == "max")
try:
    state.set("bad")
    check("state invalid raises", False)
except ValueError:
    check("state invalid raises", True)

print(f"\n===== {len(PASS)} passed, {len(FAIL)} failed =====")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
