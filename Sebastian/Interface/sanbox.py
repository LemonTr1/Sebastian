import base64
import docker
import shlex

class SandboxExecutor:
    """安全地在 Docker 容器中执行命令"""

    def __init__(self, image="sandbox:latest", timeout=30, memory_limit="256m",
                 cpu_quota=50000, network_access=False, allow_install=False):
        self.client = docker.from_env()
        self.image = image
        self.timeout = timeout
        self.memory_limit = memory_limit
        self.cpu_quota = cpu_quota  # CPU 限制，微秒级（如 50000 = 0.5核）
        self.network_access = network_access
        self.allow_install = allow_install  # 是否允许执行 apt 安装

    def run(self, command: str, lang: str = "shell", env_vars=None, timeout=None):
        """
        执行命令并返回结果
        lang: shell / python
        command: 要执行的代码或命令
        """
        container = None
        try:
            # 1. 根据语言包装命令
            full_cmd = self._wrap_command(command, lang)

            # 2. 创建容器（使用临时文件系统）
            container = self.client.containers.run(
                self.image,
                command=full_cmd,
                detach=True,
                mem_limit=self.memory_limit,
                nano_cpus=int(self.cpu_quota * 1000),  # 转换为纳核
                network_mode="none" if not self.network_access else "bridge",
                read_only=True,  # 文件系统只读
                tmpfs={"/tmp": "size=64m"},  # 临时可写区
                security_opt=["no-new-privileges:true"],
                cap_drop=["ALL"],  # 删除所有能力
                cap_add=["NET_BIND_SERVICE"] if self.network_access else [],
                environment=env_vars or {},
                volumes=None,
                remove=False,  # 最后手动删除
            )

            # 3. 超时控制
            timeout = timeout or self.timeout
            try:
                result = container.wait(timeout=timeout)
                exit_code = result['StatusCode']
            except Exception:
                # 超时，强制杀死
                container.kill()
                exit_code = -1

            # 4. 收集输出
            logs = container.logs(stdout=True, stderr=True).decode('utf-8', errors='replace')

            return {
                "success": exit_code == 0,
                "stdout": logs,
                "exit_code": exit_code
            }

        except docker.errors.ImageNotFound:
            raise RuntimeError(f"沙箱镜像 {self.image} 不存在，请先构建")
        finally:
            if container:
                try:
                    container.remove(force=True)
                except:
                    pass

    def _wrap_command(self, command: str, lang: str) -> str:
        """将用户代码包装成可执行的 shell 命令"""
        if lang == "shell":
            return f"/bin/bash -c {shlex.quote(command)}"

        elif lang == "python":
            # 将代码写入临时文件并执行
            encoded = base64.b64encode(command.encode('utf-8')).decode('ascii')
            return f"/bin/bash -c 'echo {encoded} | base64 -d | python3'"

        else:
            raise ValueError(f"不支持的语言: {lang}")