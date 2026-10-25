import os
import subprocess
import shutil
from typing import Literal
from pathlib import Path
import json
from src.logs.app_log import get_log

logger = get_log()

HOME = Path.home()

DEFAULT_SETTINGS = Path(__file__).parent.parent / "settings.json"

SETTINGS = Path.home() / ".sebastian" / "settings.json"

# 允许传入沙箱的环境变量白名单：只放行与命令执行相关的基础变量，避免 API Key 等密钥泄漏
ENV_PASSTHROUGH = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TERM", "TZ", "USER", "SHELL", "TMPDIR")

class BubblewrapSandbox:
    _disabled_warned = False

    def __init__(self):
        self._check_bwrap()
        self.config = self._load_config()

    def _load_config(self):
        """默认配置与用户配置合并：标量以用户为准，目录清单取并集，避免局部配置丢失安全默认值。"""
        try:
            defaults = self._read_sandbox_section(DEFAULT_SETTINGS)
        except Exception as e:
            logger.error(f"默认配置 {DEFAULT_SETTINGS} 读取失败：{str(e)}")
            defaults = {}

        try:
            user = self._read_sandbox_section(SETTINGS)
        except FileNotFoundError:
            logger.warning(f"未找到用户配置文件 {SETTINGS}，将使用默认配置。")
            user = {}
        except json.JSONDecodeError as e:
            logger.error(f"用户配置文件 {SETTINGS} 解析失败：{str(e)}，将使用默认配置。")
            user = {}
        except Exception as e:
            logger.warning(f"用户配置文件 {SETTINGS} 出现错误: {str(e)}，将使用默认配置。")
            user = {}

        merged = {**defaults, **user}
        for key in ("deny_read", "read_only"):
            # 只有任一侧声明了清单才生成该键，避免空列表污染配置语义
            if key in defaults or key in user:
                merged[key] = list(dict.fromkeys(defaults.get(key, []) + user.get(key, [])))
        return merged

    @staticmethod
    def _read_sandbox_section(path: Path) -> dict:
        with open(str(path), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("sandbox", data)

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


    def _sandbox_env(self) -> dict:
        env = {k: os.environ[k] for k in ENV_PASSTHROUGH if k in os.environ}
        env["HOME"] = str(HOME)
        env.setdefault("PATH", "/usr/local/bin:/usr/bin:/bin")
        for k in self.config.get("env_allow", []):
            if k in os.environ:
                env[k] = os.environ[k]
        return env

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
