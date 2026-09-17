"""提问客户端 — 线程安全，可在任意线程调用

每次提问启动独立 Python 子进程运行 question_dialog.py，
通过 JSON 文件 IPC 通信，天然满足 tkinter 的主线程要求。

与 ApprovalClient 的差异：
- 结果为结构化 dict（status/answer/...），而非布尔值
- proc.wait() 带超时兜底，避免子进程卡死永久挂住 Agent
- 取锁带超时，抢不到返回 busy 而非无限阻塞
- 提供 is_dialog_available() 供调用方在无图形环境时优雅降级
"""
import importlib.util
import json
import os
import platform
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Optional


def is_dialog_available() -> tuple[bool, str]:
    """预检能否弹出交互窗口。

    只做环境变量与模块存在性判断，不在主进程里 tk.Tk() 试探——
    那会在 Agent 进程内创建 Tcl 解释器并引入线程亲和与资源泄漏问题。
    """
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return False, "未检测到图形显示环境（DISPLAY/WAYLAND_DISPLAY 未设置）"
    if importlib.util.find_spec("tkinter") is None:
        return False, "未安装 tkinter（Debian/Ubuntu 需 sudo apt install python3-tk）"
    return True, ""


def _empty(status: str, error: str) -> dict:
    return {
        "status": status,
        "answer": None,
        "selected_option": None,
        "is_free_text": False,
        "error": error,
    }


class QuestionClient:
    """线程安全的提问客户端。

    设计原理（与 ApprovalClient 同构）：
    - 每次 ask() 调用写请求到临时 JSON 文件
    - 用 subprocess.Popen 启动独立 Python 进程运行弹窗
    - 弹窗进程有自己的 Tcl/Tk 事件循环，与主程序完全隔离
    - proc.wait() 阻塞等待用户操作完成后读取结果 JSON
    """

    def __init__(
        self,
        dialog_script_path: Optional[str] = None,
        theme: str = "dark",
        lock_wait: int = 10,
    ):
        """
        Args:
            dialog_script_path: question_dialog.py 的绝对路径。
                                为 None 时自动在同目录下查找。
            theme: "light" | "dark" | "blue"
            lock_wait: 等待上一轮提问结束的秒数，超时返回 busy
        """
        if dialog_script_path:
            self.dialog_script = dialog_script_path
        else:
            self.dialog_script = str(Path(__file__).parent / "question_dialog.py")
        self.theme = theme
        self.lock_wait = lock_wait
        self._lock = threading.Lock()

    def ask(
        self,
        question: str,
        options: Optional[list] = None,
        timeout: int = 300,
    ) -> dict:
        """弹出提问窗口，阻塞等待用户作答。

        可在任意线程安全调用（包括 daemon thread）。本方法不抛异常，
        所有失败路径都返回带 status 的 dict。

        Returns:
            {"status": "answered"|"timeout"|"cancelled"|"busy"|"error",
             "answer": str | None, "selected_option": str | None,
             "is_free_text": bool, "error": str（仅失败时）}
        """
        options = list(options) if options else []

        if not self._lock.acquire(timeout=self.lock_wait):
            return _empty("busy", "已有另一个提问窗口正在等待回答")

        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix="_q.json", delete=False, encoding="utf-8"
            ) as f:
                req_file = Path(f.name)
                result_file = req_file.with_suffix(".result.json")
                json.dump(
                    {
                        "result_file": str(result_file),
                        "question": question,
                        "options": options,
                        "timeout": timeout,
                        "theme": self.theme,
                    },
                    f,
                    ensure_ascii=False,
                )

            try:
                cmd = [sys.executable, self.dialog_script, str(req_file)]

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
                except OSError as e:
                    return _empty("error", f"无法启动提问窗口进程：{e}")

                # `wait` 是兜底：弹窗自身倒计时失效时也不能让 Agent 永久阻塞
                wait_seconds = (timeout + 30) if (timeout and timeout > 0) else None
                try:
                    proc.wait(timeout=wait_seconds)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                    return _empty("timeout", "提问窗口未在预期时间内返回结果")

                if not result_file.exists():
                    return _empty("error", "提问窗口异常退出，未返回结果")

                try:
                    with open(result_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except (json.JSONDecodeError, OSError) as e:
                    return _empty("error", f"提问结果解析失败：{e}")

                if not isinstance(data, dict) or "status" not in data:
                    return _empty("error", "提问结果格式非法")
                return data
            finally:
                for path in (req_file, result_file, Path(f"{result_file}.tmp")):
                    try:
                        path.unlink(missing_ok=True)
                    except OSError:
                        pass
        finally:
            self._lock.release()