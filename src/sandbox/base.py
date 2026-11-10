import json
import os
import sys
from pathlib import Path

from src.logs.app_log import get_log

logger = get_log()

HOME = Path.home()

DEFAULT_SETTINGS = Path(__file__).parent.parent / "settings.json"

SETTINGS = Path.home() / ".sebastian" / "settings.json"

# 允许传入沙箱的环境变量白名单：只放行与命令执行相关的基础变量，避免 API Key 等密钥泄漏
ENV_PASSTHROUGH = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TERM", "TZ", "USER", "SHELL", "TMPDIR")

DEFAULT_PATH = (
    "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
    if sys.platform == "darwin"
    else "/usr/local/bin:/usr/bin:/bin"
)

# 配置未声明的键直接使用这里的代码内默认值
DEFAULT_CONFIG = {
    "enabled": True,
    "unshare_net": True,
    "timeout": 180,
    "deny_read": [],
    "read_only": [],
}


class BaseSandbox:
    """沙箱后端公共逻辑：配置读取、环境变量白名单、统一运行结果结构。"""

    _disabled_warned = False

    def __init__(self):
        self._check_available()
        self.config = self._load_config()

    def _check_available(self) -> None:
        raise NotImplementedError

    def _load_config(self):
        return load_sandbox_config()

    @staticmethod
    def _read_sandbox_section(path: Path) -> dict:
        with open(str(path), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("sandbox", data)

    def _sandbox_env(self) -> dict:
        env = {k: os.environ[k] for k in ENV_PASSTHROUGH if k in os.environ}
        env["HOME"] = str(HOME)
        env.setdefault("PATH", DEFAULT_PATH)
        for k in self.config.get("env_allow", []):
            if k in os.environ:
                env[k] = os.environ[k]
        return env

    def run(self, command: str, timeout: int = 180) -> dict:
        raise NotImplementedError


def load_sandbox_config() -> dict:
    """读取 settings.json 的 sandbox 段。

    用户配置存在时：标量优先取用户值，缺失时取默认配置的同名键；
    deny_read / read_only 只要用户声明了该字段就以用户为准（空列表同样生效），未声明时沿用默认配置。
    用户文件缺失或不可解析时回退到默认配置；默认配置也缺的键用 DEFAULT_CONFIG 兜底。
    """
    try:
        defaults = BaseSandbox._read_sandbox_section(DEFAULT_SETTINGS)
    except Exception as e:
        logger.error(f"默认配置 {DEFAULT_SETTINGS} 读取失败：{str(e)}")
        defaults = {}

    try:
        user = BaseSandbox._read_sandbox_section(SETTINGS)
    except FileNotFoundError:
        logger.warning(f"未找到用户配置文件 {SETTINGS}，将使用默认配置。")
        user = None
    except json.JSONDecodeError as e:
        logger.error(f"用户配置文件 {SETTINGS} 解析失败：{str(e)}，将使用默认配置。")
        user = None
    except Exception as e:
        logger.warning(f"用户配置文件 {SETTINGS} 出现错误: {str(e)}，将使用默认配置。")
        user = None

    # 用户声明的字段覆盖默认配置；未声明的名单字段仍沿用默认配置
    config = defaults if user is None else {**defaults, **user}

    merged = {**DEFAULT_CONFIG, **config}
    for key in ("deny_read", "read_only"):
        merged[key] = list(dict.fromkeys(merged.get(key, [])))
    return merged
