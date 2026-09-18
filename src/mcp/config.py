"""MCP 客户端配置：读取 settings.json 中的 `mcp` 段。

查找顺序与沙箱一致：优先用户配置 ~/.sebastian/settings.json，
缺失或损坏时回退到项目内置的 src/settings.json。
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from src.logs.app_log import get_log

logger = get_log()

SETTINGS = Path.home() / ".sebastian" / "settings.json"
DEFAULT_SETTINGS = Path(__file__).resolve().parent.parent / "settings.json"

SECTION = "mcp"
DEFAULT_CONNECT_TIMEOUT = 30.0

# 仅识别 ${VAR} 形式；$VAR、${1VAR} 等写法不做处理，原样传给子进程
_ENV_REF_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _expand_env_value(server: str, key: str, value: str) -> str:
    """展开 `env` 值中的 `${VAR}` 环境变量引用。

    让 settings.json 只保存引用而非明文机密（如 `${GITHUB_TOKEN}`），
    真实值由进程环境提供。未定义的变量记 WARNING 并原样保留字面量，
    便于用户从日志里直接定位漏配的变量，而不是静默传空值。
    """

    def _replace(match: re.Match[str]) -> str:
        var = match.group(1)
        resolved = os.environ.get(var)
        if resolved is None:
            logger.warning(
                f"MCP server `{server}` 的 env `{key}` 引用了未定义的环境变量 "
                f"${{{var}}}，已按字面量保留。"
            )
            return match.group(0)
        return resolved

    return _ENV_REF_PATTERN.sub(_replace, value)


@dataclass
class McpServerConfig:
    """单个 stdio MCP server 的定义。"""

    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None
    enabled: bool = True

    def transport_kwargs(self) -> dict:
        """转成 StdioTransport 的构造参数（cwd/env 留空时用 SDK 默认值）。"""
        kwargs: dict = {"command": self.command, "args": list(self.args)}
        if self.env:
            kwargs["env"] = dict(self.env)
        if self.cwd:
            kwargs["cwd"] = self.cwd
        return kwargs


def _read_section(path: Path) -> dict | None:
    """读取配置文件中的 mcp 段；文件缺失、损坏或段类型不对时返回 None。"""
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        logger.error(f"MCP 配置 {path} 解析失败，已忽略：{e}")
        return None
    except OSError as e:
        logger.warning(f"MCP 配置 {path} 读取失败，已忽略：{e}")
        return None

    if not isinstance(data, dict):
        logger.warning(f"MCP 配置 {path} 顶层不是对象，已忽略。")
        return None

    section = data.get(SECTION)
    if section is None:
        return None
    if not isinstance(section, dict):
        logger.warning(f"MCP 配置 {path} 中的 `{SECTION}` 不是对象，已忽略。")
        return None
    return section


def load_mcp_settings() -> dict:
    """返回生效的 mcp 配置段（用户配置优先，否则用项目内置默认）。"""
    return _read_section(SETTINGS) or _read_section(DEFAULT_SETTINGS) or {}


def connect_timeout() -> float:
    """initialize 握手的超时秒数，非法值回退到默认。"""
    raw = load_mcp_settings().get("connect_timeout", DEFAULT_CONNECT_TIMEOUT)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        logger.warning(
            f"MCP connect_timeout 非法（{raw!r}），改用默认 {DEFAULT_CONNECT_TIMEOUT}s。"
        )
        return DEFAULT_CONNECT_TIMEOUT
    return value if value > 0 else DEFAULT_CONNECT_TIMEOUT


def _parse_server(name: str, item: object) -> McpServerConfig | None:
    """校验单条 server 定义，非法时记日志并返回 None（不影响其余 server）。"""
    if not isinstance(item, dict):
        logger.warning(f"MCP server `{name}` 定义不是对象，已跳过。")
        return None

    command = item.get("command")
    if not isinstance(command, str) or not command.strip():
        logger.warning(f"MCP server `{name}` 缺少有效的 `command`，已跳过。")
        return None

    args = item.get("args") or []
    if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
        logger.warning(f"MCP server `{name}` 的 `args` 必须是字符串数组，已跳过。")
        return None

    env = item.get("env") or {}
    if not isinstance(env, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in env.items()
    ):
        logger.warning(f"MCP server `{name}` 的 `env` 必须是字符串键值对，已跳过。")
        return None

    env = {k: _expand_env_value(name, k, v) for k, v in env.items()}

    cwd = item.get("cwd")
    if cwd is not None and not isinstance(cwd, str):
        logger.warning(f"MCP server `{name}` 的 `cwd` 必须是字符串，已跳过。")
        return None

    return McpServerConfig(
        name=name,
        command=command.strip(),
        args=list(args),
        env=dict(env),
        cwd=str(Path(cwd).expanduser()) if cwd else None,
        enabled=bool(item.get("enabled", True)),
    )


def load_servers() -> dict[str, McpServerConfig]:
    """解析全部 server 定义。

    顶层 `enabled` 为 false 时整体关闭（默认 true）；单条定义非法只跳过该条。
    """
    section = load_mcp_settings()
    if not section:
        return {}
    if not bool(section.get("enabled", True)):
        logger.debug("MCP 已在 settings.json 中全局关闭，未加载任何 server。")
        return {}

    raw = section.get("servers")
    if not isinstance(raw, dict):
        if raw is not None:
            logger.warning("MCP `servers` 不是对象，未加载任何 server。")
        return {}

    servers: dict[str, McpServerConfig] = {}
    for name, item in raw.items():
        cfg = _parse_server(name, item)
        if cfg is not None:
            servers[name] = cfg
    return servers


def get_server(name: str) -> McpServerConfig | None:
    """按名字取单个 server 定义，未配置或已全局关闭时返回 None。"""
    return load_servers().get(name)