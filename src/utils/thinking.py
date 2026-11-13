"""思考强度 → OpenAI 兼容请求参数。

只按 BASE_URL 识别厂商，不维护模型切换清单；模型名只用于少数「强制思考、
不可关闭」的例外判断。返回值可直接展开进 chat.completions.create。
"""

LEVELS = ("off", "medium", "max")

LEVEL_LABELS = {
    "off": "关闭",
    "medium": "中等（默认）",
    "max": "最高",
}

# 厂商识别片段；按最长匹配优先，避免代理域名误判
PROVIDER_PATTERNS: dict[str, tuple[str, ...]] = {
    "deepseek": ("api.deepseek.com",),
    "qwen": ("dashscope.aliyuncs.com", "qwencloudapi.com"),
    "glm": ("bigmodel.cn",),
    "kimi": ("moonshot.cn", "platform.kimi.com", "api.kimi.com"),
    "grok": ("api.x.ai", "x.ai"),
    "openai": ("api.openai.com", "openai.azure.com"),
    "claude": ("api.anthropic.com", "anthropic"),
    "gemini": ("generativelanguage.googleapis.com", "googleapis.com"),
}

# 这些模型强制思考，没有“关闭”档位
FORCED_THINKING_PREFIXES = (
    "glm-5.3",
    "glm-4.7",
    "kimi-k3",
    "kimi-k2.7-code",
    "grok-4.",
    "gpt-6-astra",
    "gpt-6.1-sol",
    "claude-opus-5-5",
    "claude-fable-5-1",
    "claude-sonnet-5-5",
    "gemini-4-argon",
    "gemini-3.",
    "qwen3.8-2.4t",
)


def detect_provider(base_url: str | None) -> str | None:
    """从 BASE_URL 识别厂商；未识别返回 None。"""
    url = (base_url or "").strip().lower().rstrip("/")
    if not url:
        return None

    best_provider = None
    best_len = 0
    for provider, patterns in PROVIDER_PATTERNS.items():
        for pattern in patterns:
            if pattern in url and len(pattern) > best_len:
                best_provider = provider
                best_len = len(pattern)
    return best_provider


def is_forced_thinking(model: str | None) -> bool:
    name = (model or "").strip().lower()
    return any(name.startswith(prefix) for prefix in FORCED_THINKING_PREFIXES)


def is_off_supported(provider: str | None, model: str | None) -> bool:
    """该厂商/模型是否支持关闭思考。"""
    name = (model or "").strip().lower()
    if provider in ("grok", "gemini"):
        return False
    if provider == "kimi":
        return name.startswith("kimi-k2.6")
    if provider == "claude":
        return name.startswith("claude-haiku")
    return not is_forced_thinking(model)


def thinking_options(provider: str | None, model: str | None) -> list[dict]:
    """返回三档菜单项；不可用档位带 available=False 与原因。"""
    off_supported = is_off_supported(provider, model)
    if off_supported:
        note = ""
    elif is_forced_thinking(model):
        note = "该模型强制思考，不支持关闭"
    else:
        note = "该厂商模型不支持关闭思考"
    return [
        {
            "level": "off",
            "label": LEVEL_LABELS["off"],
            "available": off_supported,
            "note": note,
        },
        {
            "level": "medium",
            "label": LEVEL_LABELS["medium"],
            "available": True,
            "note": "",
        },
        {
            "level": "max",
            "label": LEVEL_LABELS["max"],
            "available": True,
            "note": "",
        },
    ]


def build_thinking_kwargs(provider: str | None, model: str | None, level: str) -> dict:
    """构造思考参数；不可用档位或未识别厂商返回空字典。"""
    if level not in LEVELS:
        raise ValueError(f"未知思考强度：{level}")
    if provider is None:
        return {}
    if level == "off" and not is_off_supported(provider, model):
        return {}

    if provider == "deepseek":
        if level == "off":
            return {"extra_body": {"thinking": {"type": "disabled"}}}
        effort = "high" if level == "medium" else "max"
        return {
            "reasoning_effort": effort,
            "extra_body": {"thinking": {"type": "enabled"}},
        }

    if provider == "qwen":
        if level == "off":
            return {"extra_body": {"enable_thinking": False}}
        effort = "medium" if level == "medium" else "xhigh"
        return {
            "extra_body": {"enable_thinking": True, "reasoning_effort": effort}
        }

    if provider == "glm":
        if level == "off":
            return {"extra_body": {"thinking": {"type": "disabled"}}}
        kwargs = {"extra_body": {"thinking": {"type": "enabled"}}}
        name = (model or "").lower()
        if name.startswith(("glm-5.3", "glm-5.2")):
            kwargs["reasoning_effort"] = "high" if level == "medium" else "max"
        return kwargs

    if provider == "kimi":
        name = (model or "").lower()
        if name.startswith("kimi-k3"):
            return {"reasoning_effort": "high" if level == "medium" else "max"}
        if name.startswith("kimi-k2.6"):
            return {"extra_body": {"thinking": {"type": "disabled" if level == "off" else "enabled"}}}
        # kimi-k2.7-code 等：强制思考，无 effort 档位
        if level == "off":
            return {}
        return {"extra_body": {"thinking": {"type": "enabled"}}}

    if provider == "grok":
        return {"reasoning_effort": "medium" if level == "medium" else "xhigh"}

    if provider == "openai":
        if level == "off":
            return {"reasoning_effort": "none"}
        return {"reasoning_effort": "medium" if level == "medium" else "xhigh"}

    if provider == "claude":
        if level == "off":
            return {"extra_body": {"thinking": {"type": "disabled"}}}
        return {
            "extra_body": {
                "thinking": {"type": "adaptive"},
                "output_config": {"effort": "medium" if level == "medium" else "max"},
            }
        }

    if provider == "gemini":
        return {"reasoning_effort": "medium" if level == "medium" else "high"}

    return {}
