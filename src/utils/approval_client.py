"""审批客户端 — 线程安全，可在任意线程调用

每次审批启动独立 Python 子进程运行 approval_dialog.py，
通过 JSON 文件 IPC 通信，天然满足 tkinter 的主线程要求。
"""
import threading
from pathlib import Path
from typing import Optional

from src.logs.app_log import get_log
from src.utils.dialog_common import run_dialog_script
from src.utils.interaction import gui_available, terminal_confirm, terminal_ok

logger = get_log()


class ApprovalClient:
    """零线程安全的审批客户端。

    设计原理：
    - 每次 ask() 调用写请求到临时 JSON 文件
    - 用 subprocess.Popen 启动独立 Python 进程运行弹窗
    - 弹窗进程有自己的 Tcl/Tk 事件循环，与主程序完全隔离
    - proc.wait() 阻塞等待用户操作完成后读取结果 JSON
    """

    def __init__(
        self,
        dialog_script_path: Optional[str] = None,
        theme: str = "dark",
    ):
        """
        Args:
            dialog_script_path: approval_dialog.py 的绝对路径。
                                为 None 时自动在同目录下查找。
            theme: "light" | "dark" | "blue"
        """
        if dialog_script_path:
            self.dialog_script = dialog_script_path
        else:
            self.dialog_script = str(Path(__file__).parent / "approval_dialog.py")
        self.theme = theme
        self._lock = threading.Lock()

    def ask(
        self,
        tool_name: str,
        tool_args: Optional[dict] = None,
        timeout: Optional[int] = None,
    ) -> bool:
        """弹出审批窗口，阻塞等待用户选择。

        可在任意线程安全调用（包括 daemon thread）。

        Args:
            tool_name: 工具名称（显示在弹窗标题中）
            tool_args: 工具参数字典（显示在参数卡片中）
            timeout:  超时秒数，None 表示永不超时

        Returns:
            True 表示用户同意，False 表示拒绝或超时
        """
        with self._lock:
            tool_args = tool_args or {}

            # 无图形环境 → 直接终端降级
            available, reason = gui_available()
            if not available:
                logger.info(f"[approval] 无图形环境，降级为终端确认：{reason}")
                return terminal_confirm(tool_name, tool_args, timeout)

            data, error = run_dialog_script(
                self.dialog_script,
                {
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                    "timeout": timeout,
                    "theme": self.theme,
                },
                timeout,
            )

            # 任何未能正常取回结果的路径都必须显式降级，不能静默返回 False
            if error == "timeout":
                logger.warning("[approval] 审批窗口超时未返回")
            elif error:
                logger.warning(f"[approval] 审批窗口异常（{error}），尝试终端降级")

            if error:
                if terminal_ok():
                    return terminal_confirm(tool_name, tool_args, timeout)
                return False

            if not isinstance(data, dict):
                logger.warning("[approval] 审批结果格式非法")
                return False
            return bool(data.get("approved", False))
