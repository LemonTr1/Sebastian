"""提示符重绘：让后台日志不冲散 input() 的提示符和半截输入。

核心不是“锁住终端”，而是“擦掉当前行 -> 打印日志 -> 重画提示符 + 半截输入”。
输入串行化仍由 interaction.TERMINAL_IO_LOCK 负责；本模块只处理视觉层。
"""
from __future__ import annotations

import builtins
import os
import re
import select
import shutil
import sys
import threading

try:
    import readline
except ImportError:  # pragma: no cover - 非 POSIX 环境
    readline = None

import typer

_ORIG_INPUT = builtins.input
_ORIG_ECHO = typer.echo

_state_lock = threading.RLock()
_write_lock = threading.RLock()
_active_prompt: dict | None = None
_installed = False
_token_streams: dict[tuple[str, int], "MarkdownStream"] = {}

_ERASE_LINE = "\r\x1b[2K"


class InputTimeout(TimeoutError):
    """gated_input 在超时时间内没有拿到输入。"""


def _is_tty() -> bool:
    try:
        return bool(sys.stdin.isatty() and sys.stdout.isatty())
    except (AttributeError, ValueError):
        return False


def _wait_readable(timeout: float | None) -> bool:
    if timeout is None or timeout <= 0 or not hasattr(select, "select"):
        return True
    try:
        ready, _, _ = select.select([sys.stdin], [], [], timeout)
        return bool(ready)
    except (OSError, ValueError):
        # 测试/特殊 stdin 不支持 select 时不要误判超时
        return True


_ANSI_CSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_ANSI_OSC_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
_CTRL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def _safe(text: str) -> str:
    """去掉 ANSI 与控制字符，避免 LLM 输出注入终端。"""
    s = _ANSI_CSI_RE.sub("", str(text))
    s = _ANSI_OSC_RE.sub("", s)
    return _CTRL_RE.sub("", s)


def _color_enabled() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM", "").lower() == "dumb":
        return False
    try:
        return bool(sys.stdout.isatty())
    except (AttributeError, ValueError):
        return False


def _style(code: str, text: str) -> str:
    return f"{code}{text}\x1b[0m" if _color_enabled() else text


def _inline(text: str) -> str:
    """行内 Markdown：粗体/斜体/行内代码/链接。"""
    text = _safe(text)
    codes = []

    def _code(m):
        codes.append(m.group(1))
        return f"\x00{len(codes) - 1}\x00"

    text = re.sub(r"`([^`\n]+)`", _code, text)
    text = re.sub(r"\*\*(.+?)\*\*", lambda m: _style("\x1b[1m", m.group(1)), text)
    text = re.sub(r"__(.+?)__", lambda m: _style("\x1b[1m", m.group(1)), text)
    text = re.sub(r"~~(.+?)~~", lambda m: _style("\x1b[2m", m.group(1)), text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", lambda m: _style("\x1b[3m", m.group(1)), text)
    text = re.sub(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", lambda m: _style("\x1b[3m", m.group(1)), text)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: f"{m.group(1)} ({_style(chr(27) + '[2m', m.group(2))})",
        text,
    )
    for i, code in enumerate(codes):
        text = text.replace(f"\x00{i}\x00", _style("\x1b[36m", code))
    return text


def _format_line(line: str) -> str:
    """单行 Markdown -> ANSI 文本。代码块由 MarkdownStream 单独处理。"""
    line = _safe(line).rstrip("\r\n")
    stripped = line.strip()
    if not stripped:
        return ""

    m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
    if m:
        return _style("\x1b[1m\x1b[36m", _inline(m.group(2)))

    if re.fullmatch(r"[-*_]{3,}", stripped):
        width = max(10, min(60, shutil.get_terminal_size((80, 20)).columns - 1))
        return _style("\x1b[2m", "─" * width)

    m = re.match(r"^(\s*)>\s?(.*)$", line)
    if m:
        return m.group(1) + _style("\x1b[2m", "│ ") + _inline(m.group(2))

    m = re.match(r"^(\s*)[-*+]\s+(.*)$", line)
    if m:
        return m.group(1) + "• " + _inline(m.group(2))

    m = re.match(r"^(\s*\d+\.)\s+(.*)$", line)
    if m:
        return m.group(1) + " " + _inline(m.group(2))

    if stripped.startswith("|") and stripped.endswith("|"):
        return _style("\x1b[2m", line)

    return _inline(line)


class MarkdownStream:
    """按行缓冲的流式 Markdown 渲染器。"""

    def __init__(self, agent: str):
        self.agent = agent
        self.buffer = ""
        self.in_code = False

    def feed(self, token: str) -> None:
        self.buffer += str(token)
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            self.emit_line(line)

    def flush(self) -> None:
        if self.buffer:
            self.emit_line(self.buffer)
            self.buffer = ""

    def emit_line(self, line: str) -> None:
        stripped = line.strip()
        if stripped.startswith("```"):
            if self.in_code:
                self.in_code = False
                emit(_style("\x1b[2m", "└─"), agent=self.agent, nl=True)
            else:
                self.in_code = True
                lang = stripped[3:].strip()
                title = f"┌─ code{f' ({lang})' if lang else ''}"
                emit(_style("\x1b[2m", title), agent=self.agent, nl=True)
            return
        if self.in_code:
            emit(_safe(line), agent=self.agent, nl=True)
        else:
            emit(_format_line(line), agent=self.agent, nl=True)


def _flush_token_buffers() -> None:
    with _state_lock:
        streams = list(_token_streams.values())
        _token_streams.clear()
    for stream in streams:
        stream.flush()


def _redraw(text: str, nl: bool = True) -> None:
    with _state_lock:
        state = dict(_active_prompt) if _active_prompt else None
    if not state:
        _ORIG_ECHO(text, nl=nl)
        return

    prompt = state.get("prompt", "")
    header = state.get("header", "") or ""
    buffer = ""
    if not state.get("hidden") and readline is not None:
        try:
            buffer = readline.get_line_buffer()
        except Exception:
            buffer = ""

    body = text
    if nl and not body.endswith("\n"):
        body += "\n"

    # 先擦掉当前 prompt 行，再向上擦掉整个 header 块，
    # 然后把日志放在块上方，最后重画 header + prompt + 半截输入。
    seq = _ERASE_LINE
    header_lines = header.splitlines() if header else []
    for _ in header_lines:
        seq += "\x1b[1A\r\x1b[2K"
    seq += body
    if header:
        seq += header
        if not header.endswith("\n"):
            seq += "\n"
    seq += prompt + buffer

    # 一次 write，避免擦除、日志、重画之间被其他线程插入
    sys.stdout.write(seq)
    sys.stdout.flush()


def emit(text: object = "", agent: str | None = None, nl: bool = True) -> None:
    """线程安全的普通输出；提示符活跃时自动擦行/重画。"""
    text = "" if text is None else str(text)
    with _write_lock:
        with _state_lock:
            state = _active_prompt
        if state and state.get("owner") != threading.get_ident():
            _redraw(text, nl=nl)
        else:
            _ORIG_ECHO(text, nl=nl)


def emit_token(agent: str, token: str) -> None:
    """流式输出按完整行提交，并做行级 Markdown 渲染。"""
    if not token:
        return
    key = (agent, threading.get_ident())
    with _state_lock:
        stream = _token_streams.get(key)
        if stream is None:
            stream = MarkdownStream(agent)
            _token_streams[key] = stream
    stream.feed(token)


def flush_tokens() -> None:
    """把未完成的流式行补一个换行输出。"""
    _flush_token_buffers()


def _begin_prompt(prompt: str, header: str = "") -> dict:
    global _active_prompt
    state = {
        "prompt": prompt,
        "header": header,
        "owner": threading.get_ident(),
        "hidden": False,
    }
    with _state_lock:
        _active_prompt = state
    return state


def _end_prompt(state: dict) -> None:
    global _active_prompt
    with _state_lock:
        if _active_prompt is state:
            _active_prompt = None


def _drain_tty_input() -> None:
    """超时后丢弃用户未回车的半截输入，避免串到下一个提示符。"""
    try:
        import termios
        termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)
    except Exception:
        pass


def gated_input(prompt: str = "", timeout: float | None = None, header: str = "") -> str:
    """带提示符/整块 header 登记的 input()；超时抛 InputTimeout。

    header 是问题/审批块。重绘时会把 header 和 prompt 一起擦掉再重画，
    日志只出现在整块上方，不会把块和输入行隔开。
    """
    if not _is_tty():
        return _ORIG_INPUT(prompt)

    manual_prompt = bool(header) or timeout is not None
    if manual_prompt:
        payload = ""
        if header:
            payload += header
            if not header.endswith("\n"):
                payload += "\n"
        payload += prompt
        with _write_lock:
            state = _begin_prompt(prompt, header)
            sys.stdout.write(payload)
            sys.stdout.flush()
    else:
        # 无 header、无超时：把 prompt 交给 readline，行宽/历史/退格由它维护。
        with _write_lock:
            state = _begin_prompt(prompt, header)

    try:
        if timeout is not None and not _wait_readable(timeout):
            with _write_lock:
                sys.stdout.write(_ERASE_LINE)
                sys.stdout.flush()
            _drain_tty_input()
            raise InputTimeout()

        return _ORIG_INPUT("" if manual_prompt else prompt)
    finally:
        with _write_lock:
            _end_prompt(state)


def _echo_proxy(*args, **kwargs):
    """替换 typer.echo：有活跃提示符时改走重绘。"""
    with _state_lock:
        state = _active_prompt
    if state and state.get("owner") != threading.get_ident():
        text = " ".join(str(a) for a in args) if args else ""
        emit(text, nl=kwargs.get("nl", True))
        return
    return _ORIG_ECHO(*args, **kwargs)


def install() -> None:
    """安装 typer.echo 代理；重复调用安全。"""
    global _installed
    with _state_lock:
        if _installed:
            return
        _installed = True
    typer.echo = _echo_proxy


def uninstall() -> None:
    global _installed
    with _state_lock:
        if not _installed:
            return
        _installed = False
    typer.echo = _ORIG_ECHO


def prompt_active() -> bool:
    with _state_lock:
        return _active_prompt is not None
