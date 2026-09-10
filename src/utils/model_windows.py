"""模型名 → 上下文窗口(token)解析。

优先级：settings 显式配置 > settings 自定义映射 > 内置字典(精确→最长前缀) > 兜底 128K
解析结果仅记录日志，不在终端打印。
"""
import json
from pathlib import Path

from src.logs.app_log import get_log

logger = get_log()

SETTINGS = Path.home() / ".sebastian" / "settings.json"

DEFAULT_WINDOW = 128_000

# 主流模型输入上下文上限（token）
MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    # DeepSeek
    "deepseek-chat": 64_000,
    "deepseek-reasoner": 64_000,
    "deepseek-v3": 64_000,
    "deepseek-v3.1": 128_000,
    "deepseek-v3.2": 128_000,
    "deepseek-v4-flash": 128_000,
    "deepseek-v4-pro": 128_000,
    # OpenAI
    "gpt-3.5-turbo": 16_000,
    "gpt-4": 8_000,
    "gpt-4-turbo": 128_000,
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "gpt-4.1": 1_000_000,
    "o1": 200_000,
    "o1-mini": 128_000,
    "o3": 200_000,
    "o3-mini": 200_000,
    "o4-mini": 200_000,
    # Anthropic
    "claude-3-opus": 200_000,
    "claude-3-sonnet": 200_000,
    "claude-3-haiku": 200_000,
    "claude-3.5-sonnet": 200_000,
    "claude-3.5-haiku": 200_000,
    "claude-3.7-sonnet": 200_000,
    "claude-4-sonnet": 200_000,
    "claude-4-opus": 200_000,
    "claude-4.5-sonnet": 200_000,
    # Google
    "gemini-1.5-pro": 1_000_000,
    "gemini-1.5-flash": 1_000_000,
    "gemini-2.0-flash": 1_000_000,
    "gemini-2.5-pro": 1_000_000,
    "gemini-2.5-flash": 1_000_000,
    "gemini-3-pro": 1_000_000,
    "gemini-3-flash": 1_000_000,
    # 智谱 GLM
    "glm-4-flash": 128_000,
    "glm-4-air": 128_000,
    "glm-4.5": 128_000,
    "glm-4.5-air": 128_000,
    "glm-4.6": 128_000,
    "glm-4.6-air": 128_000,
    "glm-4.7": 128_000,
    "glm-4.7-flash": 128_000,
    # 阿里 Qwen
    "qwen-max": 32_000,
    "qwen-plus": 128_000,
    "qwen-turbo": 128_000,
    "qwen2.5": 128_000,
    "qwen3": 128_000,
    "qwen-long": 1_000_000,
    # 月之暗面 Kimi
    "moonshot-v1-8k": 8_000,
    "moonshot-v1-32k": 32_000,
    "moonshot-v1-128k": 128_000,
    "kimi-k2": 128_000,
    # 字节豆包
    "doubao": 128_000,
    "doubao-1.5-pro": 256_000,
    # 零一万物
    "yi-34b": 200_000,
    "yi-large": 32_000,
    # 百度
    "ernie-4.0": 8_000,
    "ernie-4.5": 128_000,
    "ernie-speed": 128_000,
    # 腾讯
    "hunyuan": 32_000,
    "hunyuan-turbo": 32_000,
    "hunyuan-large": 256_000,
    # 讯飞
    "spark": 128_000,
    # 开源
    "llama-3": 8_000,
    "llama-3.1": 128_000,
    "llama-3.2": 128_000,
    "llama-3.3": 128_000,
    "llama-4": 256_000,
    "mistral": 32_000,
    "mistral-large": 128_000,
    "mixtral": 32_000,
    "codestral": 32_000,
}

_CACHE: dict[str, int] = {}


def _load_context_settings() -> dict:
    try:
        if SETTINGS.is_file():
            with open(str(SETTINGS), "r", encoding="utf-8") as f:
                info = json.load(f)
            return info.get("context") or {}
    except Exception as e:
        logger.warning(f"读取上下文配置失败：{e}")
    return {}


def resolve_context_window(model_name: str | None = None) -> int:
    """解析模型上下文窗口。同一进程内按模型名缓存，修改配置需重启生效。"""
    key = model_name or ""
    if key in _CACHE:
        return _CACHE[key]

    ctx = _load_context_settings()

    window = ctx.get("window_tokens")
    if window not in (None, 0, ""):
        try:
            w = int(window)
            if w > 0:
                logger.info(f"[context] settings 显式配置窗口：{w} tokens")
                _CACHE[key] = w
                return w
        except (TypeError, ValueError):
            logger.warning(f"[context] window_tokens 配置无效：{window}，忽略")

    overrides = ctx.get("model_overrides") or {}
    if model_name:
        if model_name in overrides:
            try:
                w = int(overrides[model_name])
                logger.info(f"[context] 模型 {model_name} 命中自定义映射 → {w} tokens")
                _CACHE[key] = w
                return w
            except (TypeError, ValueError):
                logger.warning(f"[context] model_overrides 中 {model_name} 的窗口无效，忽略")

        if model_name in MODEL_CONTEXT_WINDOWS:
            w = MODEL_CONTEXT_WINDOWS[model_name]
            logger.info(f"[context] 模型 {model_name} → {w} tokens")
            _CACHE[key] = w
            return w

        # 最长前缀匹配（如 gpt-4o-mini-2024-07-18 → gpt-4o-mini）
        best_key, best_w = "", 0
        for cand, w in MODEL_CONTEXT_WINDOWS.items():
            if model_name.startswith(cand) and len(cand) > len(best_key):
                best_key, best_w = cand, w
        if best_key:
            logger.info(f"[context] 模型 {model_name} 前缀匹配 {best_key} → {best_w} tokens")
            _CACHE[key] = best_w
            return best_w

    logger.info(f"[context] 未知模型 {model_name or '(空)'}，使用默认窗口 {DEFAULT_WINDOW} tokens")
    _CACHE[key] = DEFAULT_WINDOW
    return DEFAULT_WINDOW
