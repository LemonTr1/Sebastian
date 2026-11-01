"""REPL 输入：prompt_toolkit 斜杠命令补全；非 TTY 或未安装时回退到 gated_input。

后台输出（cron/后台任务/流式 token）仍走 ui_redraw → typer.echo；
prompt_toolkit 的 patch_stdout 会把这些输出安全地画在输入行上方并重绘提示符。
"""
from __future__ import annotations

import os
import sys

from src.utils import ui_redraw
from src.utils.slash_commands import SLASH_COMMANDS, match_commands, resolve_enter

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.formatted_text import ANSI
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.patch_stdout import patch_stdout
    from prompt_toolkit.shortcuts import CompleteStyle
    _PT_AVAILABLE = True
except ImportError:  # pragma: no cover - 精简安装时回退
    PromptSession = None
    _PT_AVAILABLE = False

    class Completer:
        pass

    class Completion:
        pass

    KeyBindings = CompleteStyle = ANSI = patch_stdout = None


class SlashCommandCompleter(Completer):
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if not text.startswith("/"):
            return
        for cmd in match_commands(text):
            yield Completion(
                cmd,
                start_position=-len(text),
                display=cmd,
                display_meta=SLASH_COMMANDS.get(cmd, ""),
            )


def build_key_bindings() -> KeyBindings:
    kb = KeyBindings()

    @kb.add("c-m", eager=True)  # Enter：提交
    def _(event):
        buf = event.current_buffer
        action, value = resolve_enter(buf.text)
        if action == "submit":
            if value is not None and value != buf.text:
                buf.text = value
                buf.cursor_position = len(value)
            buf.validate_and_handle()
            return
        # 多个匹配：不提交半截命令，保留菜单等待继续输入
        event.app.output.bell()

    @kb.add("c-j", eager=True)  # Ctrl-J / 粘贴中的裸换行：插入换行
    def _(event):
        event.current_buffer.insert_text("\n")

    @kb.add("escape", "enter", eager=True)  # Alt+Enter：插入换行
    def _(event):
        event.current_buffer.insert_text("\n")

    return kb


_SESSION = None


def _get_session() -> PromptSession:
    global _SESSION
    if _SESSION is None:
        _SESSION = PromptSession(
            multiline=True,
            completer=SlashCommandCompleter(),
            complete_while_typing=True,
            complete_style=CompleteStyle.MULTI_COLUMN,
            reserve_space_for_menu=6,
            key_bindings=build_key_bindings(),
        )
    return _SESSION


def _is_tty() -> bool:
    if os.environ.get("TERM", "").lower() in ("", "dumb", "unknown"):
        return False
    try:
        return bool(sys.stdin.isatty() and sys.stdout.isatty())
    except (AttributeError, ValueError):
        return False


def completing_input(prompt: str = "") -> str:
    if not _PT_AVAILABLE or not _is_tty():
        return ui_redraw.gated_input(prompt)

    # readline 的非打印标记 \001/\002 在 prompt_toolkit 里不需要
    clean = prompt.replace("\x01", "").replace("\x02", "")
    try:
        with ui_redraw.pt_prompt_active(), patch_stdout(raw=True):
            return _get_session().prompt(ANSI(clean))
    except (EOFError, KeyboardInterrupt):
        raise
    except Exception:
        # prompt_toolkit 初始化/渲染失败时退回原输入路径，保证 REPL 可用
        return ui_redraw.gated_input(prompt)
