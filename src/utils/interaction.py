"""交互传输层：优先 tkinter 子进程弹窗，不可用时降级为终端确认。

职责：
- gui_available(): 判断当前环境能否弹出 tkinter 窗口
- terminal_ok():   判断是否具备可交互终端（stdin/stdout 均为 tty）
- terminal_confirm():  终端版审批（返回 bool）
- terminal_question(): 终端版提问（返回与 QuestionClient 同构的 dict）
- TERMINAL_IO_LOCK:    全局终端 I/O 锁，与 cli REPL 共用，避免多线程抢 stdin

无图形环境时，终端降级的提示块整体着黄色加粗（typer.style），与 Agent 输出、后台
任务打印区分开；审批的决策输入走 typer.confirm（默认拒绝）。
着色仅在交互终端生效，并遵循 NO_COLOR 与 TERM=dumb 约定。

环境变量：
    SEBASTIAN_INTERACTION = auto | gui | terminal
    - auto（默认）: 自动检测图形环境，不可用则终端降级
    - gui:          强制走弹窗（失败时仍会运行兜底到终端）
    - terminal:     强制走终端确认
"""
import importlib.util
import json
import os
import re
import select
import sys
import threading
import time

import typer

INTERACTION_ENV = "SEBASTIAN_INTERACTION"
VALID_MODES = ("auto", "gui", "terminal")

# 与 cli.read_user_message 共用的终端 I/O 锁
TERMINAL_IO_LOCK = threading.Lock()

_ANSI_CSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_ANSI_OSC_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
_CTRL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")

MAX_DISPLAY_CHARS = 2000


def interaction_mode() -> str:
    value = os.environ.get(INTERACTION_ENV, "auto").strip().lower()
    return value if value in VALID_MODES else "auto"


def gui_available() -> tuple[bool, str]:
    """能否弹出 tkinter 窗口。只做环境变量与模块存在性判断，
    不在主进程里 tk.Tk() 试探（避免 Tcl 解释器的线程亲和与资源泄漏）。
    """
    mode = interaction_mode()
    if mode == "terminal":
        return False, "已强制终端模式（SEBASTIAN_INTERACTION=terminal）"
    if mode == "gui":
        return True, ""
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return False, "未检测到图形显示环境（DISPLAY/WAYLAND_DISPLAY 未设置）"
    if importlib.util.find_spec("tkinter") is None:
        return False, "未安装 tkinter（Debian/Ubuntu 需 sudo apt install python3-tk）"
    return True, ""


def terminal_ok() -> bool:
    """是否具备可交互终端（审批/提问可安全读取 stdin）"""
    try:
        return bool(sys.stdin.isatty() and sys.stdout.isatty())
    except (AttributeError, ValueError):
        return False


def sanitize(text) -> str:
    """去除 ANSI 转义与不可打印控制字符，防止 LLM 输出造成终端注入。"""
    s = str(text)
    s = _ANSI_CSI_RE.sub("", s)
    s = _ANSI_OSC_RE.sub("", s)
    s = _CTRL_RE.sub("", s)
    return s


def _truncate(text: str, limit: int = MAX_DISPLAY_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"...(已截断，共 {len(text)} 字符)"


def _emit(text: str = "") -> None:
    print(text, flush=True)


def _use_color() -> bool:
    """终端降级提示是否着色：需为交互终端，且未被 NO_COLOR / TERM=dumb 禁用。"""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM", "").lower() == "dumb":
        return False
    return terminal_ok()


def _yellow(text: str = "") -> str:
    """把文本染成黄色加粗，用于无图形环境时突出人机交互提示。"""
    if not text or not _use_color():
        return text
    return typer.style(text, fg=typer.colors.YELLOW, bold=True)


def _select_supported() -> bool:
    return os.name == "posix" and hasattr(select, "select")


def _read_line_timeout(prompt: str, timeout: float | None) -> tuple[str | None, bool]:
    """读取一行。

    Returns:
        (line, timed_out)
        - line 为 None 表示 EOF（Ctrl-D）
        - timed_out 为 True 表示等待超时
    """
    sys.stdout.write(prompt)
    sys.stdout.flush()

    if timeout is not None and timeout > 0 and _select_supported():
        try:
            ready, _, _ = select.select([sys.stdin], [], [], timeout)
        except (OSError, ValueError):
            ready = [sys.stdin]
        if not ready:
            _emit()
            return None, True

    try:
        line = sys.stdin.readline()
    except (EOFError, KeyboardInterrupt):
        _emit()
        return None, False

    if line == "":
        _emit()
        return None, False
    return line, False


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


def terminal_confirm(tool_name: str, tool_args: dict | None = None, timeout: int | None = None) -> bool:
    """终端版审批。默认拒绝（空输入/EOF/超时/非交互终端）。

    Returns:
        True 表示用户同意，False 表示拒绝或无法确认
    """
    if not terminal_ok():
        return False

    tool_args = tool_args or {}
    with TERMINAL_IO_LOCK:
        _emit()
        _emit(_yellow("=" * 56))
        _emit(_yellow(f"[审批] Agent 请求执行工具：{sanitize(tool_name)}"))
        _emit(_yellow("-" * 56))
        _emit(_yellow(_truncate(_format_args(tool_args))))
        _emit(_yellow("-" * 56))
        if timeout is not None and timeout > 0:
            _emit(_yellow(f"（{timeout} 秒内无响应将默认拒绝）"))
            # typer.confirm 自身不支持超时，先探一次 stdin 可读性再进入阻塞提问
            if _select_supported():
                try:
                    ready, _, _ = select.select([sys.stdin], [], [], timeout)
                except (OSError, ValueError):
                    ready = [sys.stdin]
                if not ready:
                    _emit(_yellow("[审批] 超时，已拒绝"))
                    return False

        try:
            approved = typer.confirm(_yellow("是否允许？"), default=False)
        except (typer.Abort, EOFError, KeyboardInterrupt):
            # typer.confirm 遇 EOF/Ctrl-C 会抛 Abort，本函数契约是不抛异常
            _emit(_yellow("[审批] 未获得输入，已拒绝"))
            return False
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
    """终端版提问：可输入选项编号或自由文本。

    Returns:
        {"status": "answered"|"timeout"|"cancelled"|"unavailable",
         "answer": str|None, "selected_option": str|None,
         "is_free_text": bool, "error": str|None}
    """
    options = list(options or [])

    if not terminal_ok():
        return _question_result("unavailable", "当前环境无图形界面且非交互终端")

    timeout = timeout if (timeout and timeout > 0) else None
    deadline = None if timeout is None else time.monotonic() + timeout

    with TERMINAL_IO_LOCK:
        _emit()
        _emit(_yellow("=" * 56))
        _emit(_yellow("[提问] Agent 需要你的回答："))
        _emit(_yellow("-" * 56))
        _emit(_yellow(_truncate(sanitize(question))))
        if options:
            _emit()
            for index, option in enumerate(options, 1):
                _emit(_yellow(f"  {index}) {_truncate(sanitize(option), 300)}"))
        if timeout is not None:
            _emit(_yellow(f"（{timeout} 秒内无响应将自动取消）"))

        while True:
            remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
            if remaining is not None and remaining <= 0:
                _emit(_yellow("[提问] 超时"))
                return _question_result("timeout", "用户在等待时间内未作答")

            line, timed_out = _read_line_timeout(_yellow("回答（编号或文本）: "), remaining)
            if timed_out:
                _emit(_yellow("[提问] 超时"))
                return _question_result("timeout", "用户在等待时间内未作答")
            if line is None:
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
                _emit(_yellow("无效编号，请重新输入"))
                continue
            if text:
                return {
                    "status": "answered",
                    "answer": text,
                    "selected_option": None,
                    "is_free_text": True,
                    "error": None,
                }
            _emit(_yellow("请先选择选项或输入回答"))
