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
        :param extra_ro_binds: 额外需要只读暴露的目录，如 ['/opt', '/usr/local']
        """
        self.allowed_dir = os.path.abspath(allowed_dir)
        self.allow_network = allow_network
        self.extra_ro_binds = extra_ro_binds or []

    def run(self, command: str, lang: str, timeout: int = 60) -> subprocess.CompletedProcess:
        """
        在沙箱中执行一条 shell 命令或一段 python 代码。
        命令通过 'bash -c' 执行，确保管道、重定向等可用。
        """
        # 1. 构建 bwrap 参数
        bwrap_args = ["bwrap"]

        # 全新挂载命名空间，根目录为空 tmpfs
        bwrap_args += ["--unshare-all"]

        # 2. 只读挂载基础系统目录（保证常用命令可用）
        for d in ["/usr", "/bin", "/lib", "/lib64", "/etc", "/opt", "/usr/local"]:
            if os.path.exists(d):
                bwrap_args += ["--ro-bind", d, d]

        # 3. 挂载 proc，dev 等虚拟文件系统
        bwrap_args += ["--proc", "/proc"]
        bwrap_args += ["--dev", "/dev"]

        # 4. 挂载临时可写的 /tmp
        bwrap_args += ["--tmpfs", "/tmp"]

        # 5. 挂载额外只读目录（如 /opt, /usr/local 等）
        for ro_dir in self.extra_ro_binds:
            if os.path.exists(ro_dir):
                bwrap_args += ["--ro-bind", ro_dir, ro_dir]

        # 6. 可读写挂载工作目录
        bwrap_args += ["--bind", self.allowed_dir, self.allowed_dir]

        # 7. 切换到工作目录
        bwrap_args += ["--chdir", self.allowed_dir]

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