import os
import subprocess
import shutil
import tempfile
from pathlib import Path

HOME = Path.home()

class BubblewrapSandbox:
    def __init__(self, workspace_dir: str = None):
        #在系统的/tmp目录下新建一个名为'bwrap_workspace_<随机后缀>'的临时目录挂载当作工作目录`workspace`
        self.workspace_dir = workspace_dir or tempfile.mkdtemp(prefix="bwrap_workspace_")
        self._check_bwrap()

    @staticmethod
    def _check_bwrap():
        if not shutil.which("bwrap"):
            raise RuntimeError(
                "bubblewrap (bwrap) 未安装。请安装: "
                "sudo apt install bubblewrap 或 sudo dnf install bubblewrap"
            )

    @staticmethod
    def _mount_stdlib(bwrap_args: list, ro: bool, host_path: str, container_path: str):
        if os.path.islink(host_path):
            target = os.readlink(host_path)
            bwrap_args.extend(["--symlink", target, container_path])
        elif os.path.isdir(host_path) and ro == True:
            bwrap_args.extend(["--ro-bind", host_path, container_path])
        elif os.path.isdir(host_path) and ro == False:
            bwrap_args.extend(["--bind", host_path, container_path])

    def run(self, command: str, cwd: str = None, timeout: int = 60,
            mount_paths: list = None, env: dict = None) -> dict:
        work_dir = cwd or self.workspace_dir
        os.makedirs(work_dir, exist_ok=True)

        bwrap_args = [
            "bwrap",
            "--unshare-all",
            "--share-net",
            "--new-session",
            #当python进程意外终止时，bwrap沙箱进程自动结束防止变成孤儿进程
            "--die-with-parent",
            #绝大多数命令行工具和Shell命令都在/usr/bin,/usr/lib,/usr/sbin中
            "--ro-bind", "/usr", "/usr",
            #很多Shell命令依赖/etc目录
            "--ro-bind", "/etc", "/etc",
        ]
        #兼容老系统（有的系统/bin和/lib不是指向/usr/bin, /usr/lib的符号链接，并且有的系统根本没/lib64）
        self._mount_stdlib(bwrap_args, True, "/lib", "/lib")
        self._mount_stdlib(bwrap_args, True, "/lib64", "/lib64")
        self._mount_stdlib(bwrap_args, True,"/bin", "/bin")
        self._mount_stdlib(bwrap_args, True,"/sbin", "/sbin")
        # DNS解析支持：修复 systemd-resolved下/etc/resolv.conf符号链接断裂问题（不然pip install无法连接）
        self._mount_stdlib(bwrap_args, True, "/run/systemd/resolve", "/run/systemd/resolve")
        # 预创建所有需RW持久化的目录，确保 _mount_stdlib 的 isdir 检查通过
        for p in [
            f"{str(HOME)}/.cache/pip",
            f"{str(HOME)}/.npm",
            f"{str(HOME)}/.local",
            f"{str(HOME)}/.cargo/registry",
            f"{str(HOME)}/.cache/pnpm",
            f"{str(HOME)}/.cache/go-build",
            f"{str(HOME)}/go",
        ]:
            os.makedirs(p, exist_ok=True)
        # npm配置文件持久化，确保沙箱内npm能读写~/.npmrc
        npmrc_path = f"{str(HOME)}/.npmrc"
        if not os.path.exists(npmrc_path):
            Path(npmrc_path).touch()
        # pip缓存管理，python安装包的临时缓存
        self._mount_stdlib(bwrap_args, False, f"{str(HOME)}/.cache/pip", f"{str(HOME)}/.cache/pip")
        # npm包管理，nodejs安装包的临时缓存，npm安装包的全局缓存
        self._mount_stdlib(bwrap_args, False, f"{str(HOME)}/.npm", f"{str(HOME)}/.npm")
        # Rust包管理，有些pip包也会调用Rust编译器编译扩展模块，cargo的缓存和安装包都在这里面
        self._mount_stdlib(bwrap_args, False, f"{str(HOME)}/.cargo/registry", f"{str(HOME)}/.cargo/registry")
        # pnpm包管理
        self._mount_stdlib(bwrap_args, False, f"{str(HOME)}/.cache/pnpm", f"{str(HOME)}/.cache/pnpm")
        # Go构建缓存，缓存go build的编译中间产物
        self._mount_stdlib(bwrap_args, False, f"{str(HOME)}/.cache/go-build", f"{str(HOME)}/.cache/go-build")
        # Go包管理，go install的二进制装在~/go/bin，module缓存在~/go/pkg/mod
        self._mount_stdlib(bwrap_args, False, f"{str(HOME)}/go", f"{str(HOME)}/go")

        bwrap_args += [
            "--proc", "/proc",
            "--dev", "/dev",
            "--tmpfs", "/tmp",
            "--bind", work_dir, "/workspace",
            # pip和pipx缓存持久化到宿主机，下载好的python包依赖库都~/.local/lib里面，命令本体在~/.local/bin中，pipx包在~/.local/pipx中
            "--bind", f"{str(HOME)}/.local", f"{str(HOME)}/.local",
            "--bind", npmrc_path, npmrc_path,
            "--chdir", "/workspace",
            "--clearenv",
            #设置PATH环境变量，因为部分的Shell命令不是内置的而是在/usr/bin或usr/sbin中，必须为这些命令设置环境变量来指明所在的文件
            "--setenv", "PATH", f"/usr/bin:/bin:/usr/sbin:/sbin:{HOME}/.local/bin:{HOME}/go/bin",
            "--setenv", "HOME", str(HOME),
            "--setenv", "USER", "sandbox",
            "--setenv", "LANG", "C.UTF-8",
            "--setenv", "LC_ALL", "C.UTF-8",
            "--setenv", "npm_config_prefix", f"{str(HOME)}/.local",
            "--setenv", "npm_config_globalconfig", "/dev/null",
            "--setenv", "PIP_USER", "1",
            "--setenv", "GOPATH", f"{HOME}/go",
            "--setenv", "GOBIN", f"{HOME}/go/bin",
            "--setenv", "GOMODCACHE", f"{HOME}/go/pkg/mod",
        ]

        if mount_paths:
            for host_path, sandbox_path, ro in mount_paths:
                flag = "--ro-bind" if ro else "--bind"
                bwrap_args.extend([flag, host_path, sandbox_path])

        if env:
            for k, v in env.items():
                bwrap_args.extend(["--setenv", k, str(v)])

        shell_args = ["/bin/bash", "-c", command]
        cmd = bwrap_args + ["--"] + shell_args

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
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

    def cleanup(self):
        if os.path.exists(self.workspace_dir):
            shutil.rmtree(self.workspace_dir, ignore_errors=True)
