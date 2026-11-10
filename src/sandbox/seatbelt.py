import shutil
import subprocess
import tempfile
from pathlib import Path

from src.logs.app_log import get_log
from src.sandbox.base import BaseSandbox, HOME

logger = get_log()

# 允许标准流与空设备写入，避免重定向被 Seatbelt 拒绝
_STDIO_WRITE_TARGETS = (
    '(subpath "/dev/fd") (literal "/dev/null") (literal "/dev/stdout") '
    '(literal "/dev/stderr") (literal "/dev/tty")'
)


def _sbl_quote(path: Path | str) -> str:
    """转义 SBPL 字符串字面量中的反斜杠与双引号。"""
    return str(path).replace("\\", "\\\\").replace('"', '\\"')


class SeatbeltSandbox(BaseSandbox):
    """macOS Seatbelt 后端：通过 sandbox-exec 生成临时 SBPL 配置实现读写/网络限制。"""

    _deprecation_warned = False

    def _check_available(self):
        if not shutil.which("sandbox-exec"):
            raise RuntimeError(
                "macOS 沙箱工具 sandbox-exec 不可用，请确认系统完整性或改用 sandbox.enabled=false"
            )
        if not SeatbeltSandbox._deprecation_warned:
            SeatbeltSandbox._deprecation_warned = True
            logger.warning(
                "[sandbox] sandbox-exec 已被 Apple 标记为弃用，当前版本仍可用；"
                "该命令不可用时请设置 sandbox.enabled=false"
            )

    def _existing_paths(self, key: str):
        for raw in self.config.get(key, []):
            path = Path(raw).expanduser().resolve()
            if path.exists():
                yield path

    @staticmethod
    def _rule(operation: str, path: Path) -> str:
        kind = "subpath" if path.is_dir() else "literal"
        return f'({operation} ({kind} "{_sbl_quote(path)}"))'

    def _build_profile(self) -> str:
        """按 SBPL「后匹配优先」语义生成配置：先放开，再逐层收紧。"""
        home = _sbl_quote(HOME)
        temp_dir = _sbl_quote(Path(tempfile.gettempdir()).resolve())

        lines = [
            "(version 1)",
            "(allow default)",
            "(deny file-write*)",
            (
                "(allow file-write* "
                f'(subpath "{home}") (subpath "{temp_dir}") '
                '(subpath "/private/tmp") (subpath "/private/var/tmp") '
                f"{_STDIO_WRITE_TARGETS})"
            ),
        ]

        for path in self._existing_paths("read_only"):
            lines.append(self._rule("deny file-write*", path))

        for path in self._existing_paths("deny_read"):
            lines.append(self._rule("deny file-read*", path))
            lines.append(self._rule("deny file-write*", path))

        if self.config.get("unshare_net", True):
            lines.append("(deny network*)")

        return "\n".join(lines)

    def run(self, command: str, timeout: int = 180) -> dict:
        if "timeout" in self.config:
            timeout = self.config["timeout"]

        shell_args = ["/bin/bash", "-c", command]

        if self.config.get("enabled", True):
            cmd = ["sandbox-exec", "-p", self._build_profile()] + shell_args
        else:
            if not SeatbeltSandbox._disabled_warned:
                SeatbeltSandbox._disabled_warned = True
                logger.warning("[sandbox] 已禁用（sandbox.enabled=false），命令将直接在宿主机执行")
            cmd = shell_args

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=self._sandbox_env(),
                cwd=str(HOME),
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
