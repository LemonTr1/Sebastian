from src.hooks.hooks_registry import get_hooks_registry
from src.logs.app_log import get_log

_logger = None

#惰性加载
def _get_logger():
    global _logger
    if _logger is None:
        _logger = get_log()
    return _logger


def log_hook(agent_name: str, tool_call: dict):
    """log every tool call request"""
    tool_name = tool_call["function"]["name"]
    args = tool_call["function"]["arguments"]
    _get_logger().info(f"{agent_name}执行了工具调用: {tool_name}: {args}")
    return None

get_hooks_registry().register_hook("PreToolUse", log_hook)