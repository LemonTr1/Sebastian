"""审批客户端 — 线程安全，可在任意线程调用

每次审批启动独立 Python 子进程运行 approval_dialog.py，
通过 JSON 文件 IPC 通信，天然满足 tkinter 的主线程要求。
"""
import json
import os
import platform
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Optional


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

            with tempfile.NamedTemporaryFile(
                mode="w", suffix="_req.json", delete=False, encoding="utf-8"
            ) as f:
                req_file = Path(f.name)
                result_file = req_file.with_suffix(".result.json")
                json.dump(
                    {
                        "result_file": str(result_file),
                        "tool_name": tool_name,
                        "tool_args": tool_args,
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

                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    **kwargs,
                )
                proc.wait()

                if result_file.exists():
                    with open(result_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    return data.get("approved", False)
                return False
            finally:
                for f in (req_file, result_file):
                    try:
                        f.unlink(missing_ok=True)
                    except Exception:
                        pass
