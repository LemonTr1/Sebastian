from src.hooks.hooks_registry import get_hooks_registry
from src.logs.app_log import get_log

logger = get_log()

def log_hook(agent_name: str, tool_call: dict):
    """log every tool call request"""
    tool_name = tool_call["function"]["name"]
    args = tool_call["function"]["arguments"]
    logger.info(f"{agent_name}发出工具调用请求: {tool_name}: {args}")
    return None

get_hooks_registry().register_hook("PreToolUse", log_hook)