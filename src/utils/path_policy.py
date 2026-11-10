"""路径策略：只按 settings.json 的 sandbox.deny_read / read_only 校验，不再硬编码路径黑名单。"""
from pathlib import Path

from src.sandbox.base import load_sandbox_config
from src.utils.exceptions import SecurityException


def _resolve(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def _within(path: Path, root: Path) -> bool:
    return path == root or path.is_relative_to(root)


def denied_roots() -> list[Path]:
    """settings.json 中禁止读写的路径（已展开 ~ 并解析符号链接）。"""
    return [_resolve(p) for p in load_sandbox_config().get("deny_read", [])]


def read_only_roots() -> list[Path]:
    """settings.json 中禁止写入的路径（已展开 ~ 并解析符号链接）。"""
    return [_resolve(p) for p in load_sandbox_config().get("read_only", [])]


def is_denied(path: str | Path, roots: list[Path] | None = None) -> bool:
    """判断路径是否命中 deny_read；可传入预计算的 roots 避免重复读取配置。"""
    real = _resolve(path)
    candidates = denied_roots() if roots is None else roots
    return any(_within(real, root) for root in candidates)


def resolve_path(path: str, must_exist: bool = True, write: bool = False) -> str:
    """展开并解析路径，仅按 settings.json 的 deny_read / read_only 校验。

    write=True 时额外拒绝 read_only 中的路径；must_exist=False 用于创建新文件。
    """
    raw = Path(path).expanduser()
    if must_exist and not raw.exists():
        raise SecurityException(f"路径不存在：`{raw}`")

    real = raw.resolve()
    config = load_sandbox_config()

    for denied in config.get("deny_read", []):
        if _within(real, _resolve(denied)):
            raise SecurityException(
                f"路径在 settings.json 的 deny_read 中，禁止访问：{real}"
            )

    if write:
        for read_only in config.get("read_only", []):
            if _within(real, _resolve(read_only)):
                raise SecurityException(
                    f"路径在 settings.json 的 read_only 中，禁止写入：{real}"
                )

    return str(real)
