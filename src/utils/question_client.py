"""提问客户端 — 线程安全，可在任意线程调用

每次提问启动独立 Python 子进程运行 question_dialog.py，
通过 JSON 文件 IPC 通信，天然满足 tkinter 的主线程要求。

与 ApprovalClient 的差异：
- 结果为结构化 dict（status/answer/...），而非布尔值
- proc.wait() 带超时兜底，避免子进程卡死永久挂住 Agent
- 取锁带超时，抢不到返回 busy 而非无限阻塞
- 提供 is_dialog_available() 供调用方在无图形环境时优雅降级
"""
import threading
from pathlib import Path
from typing import Optional

from src.logs.app_log import get_log
from src.utils.dialog_common import run_dialog_script
from src.utils.interaction import gui_available, terminal_question, terminal_ok

logger = get_log()


def is_dialog_available() -> tuple[bool, str]:
    """兼容别名：委托给 interaction.gui_available()。

    只做环境变量与模块存在性判断，不在主进程里 tk.Tk() 试探——
    那会在 Agent 进程内创建 Tcl 解释器并引入线程亲和与资源泄漏问题。
    """
    return gui_available()


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
            # 无图形环境 → 直接终端降级
            available, reason = gui_available()
            if not available:
                return terminal_question(question, options, timeout)

            data, error = run_dialog_script(
                self.dialog_script,
                {
                    "question": question,
                    "options": options,
                    "timeout": timeout,
                    "theme": self.theme,
                },
                timeout,
            )

            if error == "timeout":
                return _empty("timeout", "提问窗口未在预期时间内返回结果")
            if error == "spawn":
                return _empty("error", "无法启动提问窗口进程")
            if error == "parse":
                return _empty("error", "提问结果解析失败")
            if error == "no_result":
                # 弹窗异常退出、未产生结果 → 运行兜底
                if terminal_ok():
                    return terminal_question(question, options, timeout)
                return _empty("error", "提问窗口异常退出，未返回结果")

            if not isinstance(data, dict) or "status" not in data:
                return _empty("error", "提问结果格式非法")
            return data
        finally:
            self._lock.release()