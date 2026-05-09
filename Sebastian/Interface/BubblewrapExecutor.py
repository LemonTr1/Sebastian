import subprocess
import os
from typing import List, Optional

class BubblewrapExecutor:
    """
    基于 bubblewrap 的轻量沙箱执行器。
    每个命令在受限的文件系统和网络环境中运行，无需 root 权限。
    """

    def __init__(
        self,
        allowed_dir: str,
        allow_network: bool = False,
        extra_ro_binds: Optional[List[str]] = None,
    ):
        """
        :param allowed_dir:  允许 Agent 读写的目录（会被可读写挂载）
        :param allow_network: 是否允许网络访问（默认禁止）
        :param extra_ro_binds: 额外需要只读暴露的目录
        """
        self.allowed_dir = os.path.abspath(allowed_dir)
        self.allow_network = allow_network
        self.extra_ro_binds = extra_ro_binds or []

    def run(self, command: str, lang: str, timeout: int = 60) -> subprocess.CompletedProcess:
        """
        在沙箱中执行一条 shell 命令或一段 python 代码。
        命令通过 'bash -c' 执行，确保管道、重定向等可用。
        """
        bwrap_args = ["bwrap", "--unshare-all"]

        # 只读挂载系统目录（/usr, /bin, /lib*, /etc）
        for d in ["/usr", "/bin", "/sbin", "/lib", "/lib64", "/lib32", "/etc", "/opt", "/usr/local"]:
            if os.path.exists(d):
                bwrap_args += ["--ro-bind", d, d]

        # 可选 /var (只读) + 覆盖可写 /var/tmp
        if os.path.exists("/var"):
            bwrap_args += ["--ro-bind", "/var", "/var"]
        bwrap_args += ["--tmpfs", "/var/tmp"]

        # 虚拟文件系统
        bwrap_args += ["--proc", "/proc"]
        bwrap_args += ["--dev", "/dev"]  # 使用 bwrap 最小设备集
        bwrap_args += ["--tmpfs", "/tmp"]
        bwrap_args += ["--tmpfs", "/run"]
        bwrap_args += ["--tmpfs", "/dev/shm"]

        for ro_dir in self.extra_ro_binds:
            if os.path.exists(ro_dir):
                bwrap_args += ["--ro-bind", ro_dir, ro_dir]

        # ★ 核心：只读暴露真实目标目录，写入隔离到 /workspace (tmpfs)
        bwrap_args += ["--ro-bind", self.allowed_dir, self.allowed_dir]
        bwrap_args += ["--tmpfs", "/workspace"]
        bwrap_args += ["--chdir", "/workspace"]

        # 8. 网络控制
        if not self.allow_network:
            # --unshare-all 已经隔离了网络，但也可明确指定
            bwrap_args += ["--unshare-net"]

        # 9. 要执行的shell命令或python代码（通过 -- 分隔）
        if lang == "shell":
            bwrap_args += ["--", "bash", "-c", command]
        elif lang == "python":
            bwrap_args += ["--", "python3", "-c", command]

        # 10. 执行子进程
        try:
            result = subprocess.run(
                bwrap_args,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"命令在 {timeout}s 内未完成，已被终止")
        except FileNotFoundError:
            raise RuntimeError(
                "未找到 bwrap，请确保已安装 bubblewrap。\n"
                "Debian/Ubuntu: sudo apt install bubblewrap\n"
                "Fedora: sudo dnf install bubblewrap"
            )
        except Exception as e:
            raise Exception(f"发生错误: {str(e)}")