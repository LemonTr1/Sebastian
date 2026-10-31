"""终端交互：审批与提问，全部走 input() + 提示符重绘。

输入串行化由 TERMINAL_IO_LOCK 负责；提示符重绘由 ui_redraw 负责。
没有 Tkinter，没有子进程弹窗，也没有 SEBASTIAN_INTERACTION。
"""
import json
import os
import re
import shutil
import sys
import threading
import time

import typer

from src.utils import ui_redraw

# 与 cli.read_user_message 共用的终端 I/O 锁
TERMINAL_IO_LOCK = threading.Lock()

MAX_DISPLAY_CHARS = 2000


def terminal_ok() -> bool:
    """是否具备可交互终端（审批/提问可安全读取 stdin）。"""
    try:
        return bool(sys.stdin.isatty() and sys.stdout.isatty())
    except (AttributeError, ValueError):
        return False


def sanitize(text) -> str:
    """去除 ANSI 转义与不可打印控制字符，防止 LLM 输出造成终端注入。"""
    s = str(text)
    s = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", s)
    s = re.sub(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)", "", s)
    s = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", s)
    return s


def _truncate(text: str, limit: int = MAX_DISPLAY_CHARS) -> str:
    # 终端块最多占约 12 行；避免 2000 字在 80 列下把整屏占满
    cols = max(20, shutil.get_terminal_size((80, 20)).columns)
    limit = min(limit, cols * 12)
    if len(text) <= limit:
        return text
    return text[:limit] + f"...(已截断，共 {len(text)} 字符)"


def _emit(text: str = "") -> None:
    ui_redraw.emit(text, nl=True, allow_ansi=True)


def _use_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM", "").lower() == "dumb":
        return False
    return terminal_ok()


def _yellow(text: str = "") -> str:
    if not text or not _use_color():
        return text
    return typer.style(text, fg=typer.colors.YELLOW, bold=True)


def _cap_block(text: str, max_lines: int = 12) -> str:
    """限制审批/提问块高度，避免长参数或大量选项占满整屏。"""
    lines = str(text).splitlines()
    if len(lines) <= max_lines:
        return str(text)
    return "\n".join(lines[:max_lines] + ["...(更多内容已省略)"])


def _format_args(tool_args: dict) -> str:
    if not tool_args:
        return "  (无参数)"
    lines = []
    for key, value in tool_args.items():
        if isinstance(value, (dict, list)):
            value_str = json.dumps(value, ensure_ascii=False, indent=2)
        else:
            value_str = str(value)
        lines.append(f"  {sanitize(key)}: {sanitize(value_str)}")
    return "\n".join(lines)


def terminal_confirm(
    tool_name: str,
    tool_args: dict | None = None,
    timeout: int | None = None,
    agent_name: str | None = None,
) -> bool:
    """终端版审批。默认拒绝（空输入/EOF/超时/非交互终端）。"""
    if not terminal_ok():
        return False

    tool_args = tool_args or {}
    with TERMINAL_IO_LOCK:
        lines = ["", _yellow("=" * 56)]
        if agent_name:
            lines.append(_yellow(f"[审批] {sanitize(agent_name)} 请求执行工具：{sanitize(tool_name)}"))
        else:
            lines.append(_yellow(f"[审批] Agent 请求执行工具：{sanitize(tool_name)}"))
        lines.extend([
            _yellow("-" * 56),
            _yellow(_truncate(_format_args(tool_args))),
            _yellow("-" * 56),
        ])
        if timeout is not None and timeout > 0:
            lines.append(_yellow(f"（{timeout} 秒内无响应将默认拒绝）"))

        try:
            answer = ui_redraw.gated_input(
                _yellow("是否允许？[y/N] "),
                timeout=timeout,
                header=_cap_block("\n".join(lines)),
            )
        except ui_redraw.InputTimeout:
            _emit(_yellow("[审批] 超时，已拒绝"))
            return False
        except (EOFError, KeyboardInterrupt):
            _emit(_yellow("[审批] 未获得输入，已拒绝"))
            return False

        approved = answer.strip().lower() in ("y", "yes")
        _emit(_yellow("[审批] 已允许" if approved else "[审批] 已拒绝"))
        return approved


def _question_result(status: str, error: str | None = None) -> dict:
    return {
        "status": status,
        "answer": None,
        "selected_option": None,
        "is_free_text": False,
        "error": error,
    }


def terminal_question(question: str, options: list | None = None, timeout: int | None = None) -> dict:
    """终端版提问：可输入选项编号或自由文本。"""
    options = list(options or [])

    if not terminal_ok():
        return _question_result("unavailable", "当前环境不是交互终端")

    timeout = timeout if (timeout and timeout > 0) else None

    with TERMINAL_IO_LOCK:
        lines = [
            "",
            _yellow("=" * 56),
            _yellow("[提问] Agent 需要你的回答："),
            _yellow("-" * 56),
            _yellow(_truncate(sanitize(question))),
        ]
        if options:
            lines.append("")
            for index, option in enumerate(options, 1):
                lines.append(_yellow(f"  {index}) {_truncate(sanitize(option), 300)}"))
        if timeout is not None:
            lines.append(_yellow(f"（{timeout} 秒内无响应将自动取消）"))
        # 时限只覆盖真正等待用户作答的时间，不把等锁时间算进去
        deadline = None if timeout is None else time.monotonic() + timeout

        while True:
            remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
            if remaining is not None and remaining <= 0:
                _emit(_yellow("[提问] 超时"))
                return _question_result("timeout", "用户在等待时间内未作答")

            try:
                line = ui_redraw.gated_input(
                    _yellow("回答（编号或文本）: "),
                    timeout=remaining,
                    header=_cap_block("\n".join(lines)),
                )
            except ui_redraw.InputTimeout:
                _emit(_yellow("[提问] 超时"))
                return _question_result("timeout", "用户在等待时间内未作答")
            except (EOFError, KeyboardInterrupt):
                _emit(_yellow("[提问] 已取消"))
                return _question_result("cancelled", "用户中断了回答")

            text = line.strip()
            if options and text.isdigit():
                idx = int(text)
                if 1 <= idx <= len(options):
                    chosen = options[idx - 1]
                    _emit(_yellow(f"[提问] 已选择：{sanitize(chosen)}"))
                    return {
                        "status": "answered",
                        "answer": chosen,
                        "selected_option": chosen,
                        "is_free_text": False,
                        "error": None,
                    }
                # 超出编号范围时按自由文本接受（例如用户想回答数字 8080）
                pass

            if text:
                _emit(_yellow("[提问] 已收到回答"))
                return {
                    "status": "answered",
                    "answer": text,
                    "selected_option": None,
                    "is_free_text": True,
                    "error": None,
                }

            _emit(_yellow("回答不能为空，请重新输入"))
