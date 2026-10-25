"""审批 / 提问弹窗的公共层：主题色、基础样式、居中定位、结果文件原子写，
以及客户端侧的「建请求文件 → 起子进程 → 等结果 → 清理」公共流程。

两个弹窗（approval_dialog / question_dialog）各自运行在独立 Python 子进程里，
必须以脚本方式直接执行，因此本模块只依赖标准库：
- 作为脚本运行：脚本目录在 sys.path[0]，走 `from dialog_common import ...`
- 被包导入时：走相对导入
"""
import json
import logging
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

THEMES = {
    "light": {
        "bg": "#f5f5f5", "fg": "#1a1a1a",
        "accent": "#4CAF50", "danger": "#f44336",
        "card": "#ffffff", "border": "#dddddd",
    },
    "dark": {
        "bg": "#1e1e1e", "fg": "#d4d4d4",
        "accent": "#4ec9b0", "danger": "#f44747",
        "card": "#252526", "border": "#3e3e42",
    },
    "blue": {
        "bg": "#0a1929", "fg": "#e0e0e0",
        "accent": "#3182ce", "danger": "#e53e3e",
        "card": "#132f4c", "border": "#1e4976",
    },
}


def get_theme(name: str) -> dict:
    return THEMES.get(name, THEMES["dark"])


def apply_base_style(style, theme: dict) -> None:
    """两个弹窗共用的 ttk 样式。"""
    style.configure("TFrame", background=theme["bg"])
    style.configure("TLabel", background=theme["bg"], foreground=theme["fg"], font=("Noto Sans CJK SC", 11))
    style.configure(
        "Header.TLabel",
        font=("Noto Sans CJK SC", 14, "bold"),
        foreground=theme["fg"],
        background=theme["bg"],
    )
    style.configure("Dim.TLabel", font=("Noto Sans CJK SC", 9), foreground="#888888", background=theme["bg"])


def center_window(window, width: int, height: int) -> None:
    """按最终尺寸把窗口居中；先 update_idletasks 保证尺寸已生效。"""
    window.update_idletasks()
    screen_w, screen_h = window.winfo_screenwidth(), window.winfo_screenheight()
    window.geometry(f"{width}x{height}+{(screen_w - width) // 2}+{(screen_h - height) // 2}")


def write_result_atomic(path: str, payload: dict) -> None:
    """先写 .tmp 再 os.replace，避免客户端读到半截 JSON。异常由调用方处理。"""
    tmp_file = f"{path}.tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    os.replace(tmp_file, path)


def run_dialog_script(dialog_script: str, payload: dict, timeout: int | None = None) -> tuple[dict | None, str]:
    """启动弹窗子进程并取回结果。

    Returns:
        (data, error)：成功时 error 为 ""；失败时 data 为 None，error 取
        "spawn"（子进程起不来）/ "timeout"（超时被 kill）/ "no_result"（异常退出）/
        "parse"（结果文件不可解析）。各调用方按自己的语义决定降级方式。
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix="_req.json", delete=False, encoding="utf-8") as f:
        req_file = Path(f.name)
        result_file = req_file.with_suffix(".result.json")
        json.dump({**payload, "result_file": str(result_file)}, f, ensure_ascii=False)

    try:
        cmd = [sys.executable, dialog_script, str(req_file)]

        kwargs = {}
        if platform.system() == "Windows":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **kwargs,
            )
        except OSError:
            logger.debug(f"[dialog] 无法启动弹窗进程：{dialog_script}", exc_info=True)
            return None, "spawn"

        # wait 兜底：弹窗自身倒计时失效时也不能让 Agent 永久阻塞
        wait_seconds = (timeout + 30) if (timeout and timeout > 0) else None
        try:
            proc.wait(timeout=wait_seconds)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            return None, "timeout"

        if not result_file.exists():
            return None, "no_result"

        try:
            with open(result_file, "r", encoding="utf-8") as f:
                return json.load(f), ""
        except (json.JSONDecodeError, OSError):
            logger.debug("[dialog] 结果文件解析失败", exc_info=True)
            return None, "parse"
    finally:
        for path in (req_file, result_file, Path(f"{result_file}.tmp")):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logger.debug(f"[dialog] 清理临时文件失败：{path}", exc_info=True)
