import importlib
from pathlib import Path

from src.logs.app_log import get_log

_logger = get_log()

_HOOK_EVENTS = ["user_prompt_submit", "pre_tool_use", "post_completion", "stop"]
_HERE = Path(__file__).parent

for _event in _HOOK_EVENTS:
    _dir = _HERE / _event
    if not _dir.is_dir():
        continue
    for _file in sorted(_dir.glob("*.py")):
        _name = _file.stem
        if _name.startswith("_"):
            continue
        try:
            importlib.import_module(f"src.hooks.{_event}.{_name}")
        except Exception as e:
            # 钩子导入失败不能静默：HITL 等安全钩子静默丢失会导致危险操作绕过审批
            _logger.error(f"钩子模块 {_event}/{_name} 导入失败：{e}")
