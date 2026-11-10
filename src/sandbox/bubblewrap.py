import os
import subprocess
import shutil
from typing import Literal
from pathlib import Path
from src.logs.app_log import get_log
from src.sandbox.base import BaseSandbox, HOME

logger = get_log()


class BubblewrapSandbox(BaseSandbox):
    def _check_available(self):
        self._check_bwrap()

    def _check_bwrap(self):
        if not shutil.which("bwrap"):
            raise RuntimeError(
                "bubblewrap (bwrap) 未安装。请安装: "
                "sudo apt install bubblewrap 或 sudo dnf install bubblewrap"
            )

    def _mount(self, bwrap_args: list, path: str, mode: Literal["read_only", "deny_read", "allow_write"]):
        path = str(Path(path).expanduser().resolve())

        if not os.path.exists(path):
            return

        if mode == "read_only":
            bwrap_args.extend(["--ro-bind", path, path])
        elif mode == "allow_write":
            bwrap_args.extend(["--bind", path, path])
        else:
            if os.path.isdir(path):
                bwrap_args.extend(["--tmpfs", path])
            else:
                bwrap_args.extend(["--ro-bind", "/dev/null", path])

    def run(self, command: str, timeout: int = 180) -> dict:
        #基础默认配置
        bwrap_args = [
            "bwrap",
            "--new-session",
            "--die-with-parent",
            "--cap-drop", "ALL",
            "--ro-bind", "/", "/",
        ]
        self._mount(bwrap_args, "/tmp", "allow_write")
        self._mount(bwrap_args, str(HOME), "allow_write")
        bwrap_args.extend(["--chdir", str(HOME)])

        #按settings.json配置
        if self.config.get("unshare_net", True):
            bwrap_args.append("--unshare-net")
        # 其他 namespace 始终隔离
        bwrap_args.extend([
            "--unshare-pid", "--unshare-ipc",
            "--unshare-uts", "--unshare-cgroup"
        ])

        if "timeout" in self.config:
            timeout = self.config["timeout"]

        for path in self.config.get("read_only", []):
            self._mount(bwrap_args, path, "read_only")

        for path in self.config.get("deny_read", []):
            self._mount(bwrap_args, path, "deny_read")

        bwrap_args.extend(["--dev-bind", "/dev/null", "/dev/null"])

        shell_args = ["/bin/bash", "-c", command]

        if self.config.get("enabled", True):
            cmd = bwrap_args + ["--"] + shell_args
        else:
            if not BubblewrapSandbox._disabled_warned:
                BubblewrapSandbox._disabled_warned = True
                logger.warning("[sandbox] 已禁用（sandbox.enabled=false），命令将直接在宿主机执行")
            cmd = shell_args

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=self._sandbox_env()
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"命令执行超时（{timeout}秒）",
                "returncode": -1,
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "returncode": -1,
            }
