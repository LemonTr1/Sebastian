from pathlib import Path

import typer

from src.utils.exceptions import SecurityException

ABSOLUTE_SENSITIVE_DIRS = [
    "/etc",
    "/boot",
    "/root",
    "/sys",
    "/proc",
    "/dev",
    "/run",
    "/tmp",
    "/var",
]

RELATIVE_SENSITIVE_DIRS = {
    ".ssh",
    ".gnupg",
    ".aws",
    ".docker",
    ".kube",
    ".mozilla",
    ".thunderbird",
    ".config",
    ".npm",
    ".cache",
}

SENSITIVE_NAMES = {
    ".bashrc",
    ".bash_profile",
    ".zshrc",
    ".profile",
    ".zshenv",
    ".zprofile",
    "id_rsa",
    "id_ed25519",
    "id_ecdsa",
    "id_dsa",
    ".netrc",
    ".pgpass",
    ".my.cnf",
    ".npmrc",
    ".pypirc",
    ".git-credentials",
    ".bash_history",
    ".zsh_history",
    ".python_history",
    ".env",
    ".env.local",
    ".env.production",
    "credentials",
    "token",
    "secret",
}

SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".cer", ".crt", ".pub"}

SENSITIVE_NAME_KEYWORDS = (
    "secret",
    "token",
    "password",
    "credential",
    "api_key",
    "private_key",
)


def _follow_path(path: str, must_exist: bool) -> Path:
    """Expand user and follow symlinks. Fail closed on broken links."""
    raw = Path(path).expanduser()
    try:
        if must_exist:
            if not raw.exists():
                raise SecurityException(
                    f"路径不存在（或符号链接指向不存在目标）：`{raw}`"
                )
            return raw.resolve(strict=True)

        parent = raw.parent
        if not parent.exists():
            raise SecurityException(f"`{raw}`的父目录：`{parent}`不存在")
        if raw.exists():
            typer.echo(
                typer.style(
                    f"[Warning]`{raw}`存在，此操作会覆盖现有文件内容",
                    fg=typer.colors.YELLOW,
                    bold=True,
                )
            )
            return raw.resolve(strict=True)
        return parent.resolve(strict=True) / raw.name
    except SecurityException:
        raise
    except (OSError, RuntimeError) as e:
        raise SecurityException(f"无法解析路径（符号链接可能成环或目标不可达）：`{path}`") from e


def _assert_safe(real_path: Path) -> None:
    home_dir = Path.home().resolve()
    if not real_path.is_relative_to(home_dir):
        raise SecurityException(f"路径位于用户家目录外，严禁访问：{home_dir}")

    for sd in ABSOLUTE_SENSITIVE_DIRS:
        sd_path = Path(sd).resolve()
        try:
            real_path.relative_to(sd_path)
            raise SecurityException(
                f"路径位于敏感目录下，严禁访问：{sd}（完整路径：{real_path}）"
            )
        except ValueError:
            pass

    for part in real_path.parts:
        if part in RELATIVE_SENSITIVE_DIRS:
            raise SecurityException(
                f"路径包含敏感目录分量，严禁访问：'{part}'（完整路径：{real_path}）"
            )

    file_name = real_path.name
    if file_name in SENSITIVE_NAMES:
        raise SecurityException(
            f"路径为敏感文件，严禁访问：{file_name}（完整路径：{real_path}）"
        )

    if real_path.suffix.lower() in SENSITIVE_SUFFIXES:
        raise SecurityException(f"路径具有敏感扩展名，严禁访问（完整路径：{real_path}）")

    lower_name = file_name.lower()
    if any(kw in lower_name for kw in SENSITIVE_NAME_KEYWORDS):
        raise SecurityException(f"路径文件名包含敏感关键词，严禁访问（完整路径：{real_path}）")


def resolve_safe_path(path: str, must_exist: bool = True) -> str:
    real_path = _follow_path(path.strip(), must_exist=must_exist)
    _assert_safe(real_path)
    return str(real_path)
