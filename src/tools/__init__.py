import importlib
from pathlib import Path

_TOOL_PACKAGES = ["file", "code", "web", "memory", "brain"]

for _pkg in _TOOL_PACKAGES:
    _dir = Path(__file__).parent / _pkg
    if not _dir.is_dir():
        continue
    for _f in sorted(_dir.glob("*.py")):
        _name = _f.stem
        if _name.startswith("_"):
            continue
        importlib.import_module(f"src.tools.{_pkg}.{_name}")
