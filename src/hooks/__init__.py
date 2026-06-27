import importlib
from pathlib import Path

_HOOK_EVENTS = ["user_prompt_submit", "pre_tool_use", "post_tool_use", "stop"]
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
        except Exception:
            pass
