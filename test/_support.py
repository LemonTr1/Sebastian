"""测试共享支撑：把临时工作目录统一放在仓库内 `.test-tmp/`。

放在仓库内有两个原因：
1. 受限环境通常只允许写项目目录，建在 $HOME 根目录会 PermissionError；
2. 仓库位于 $HOME 之下，仍满足 path_safety 的「家目录内」约束。
"""
import atexit
import shutil
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = REPO_ROOT / ".test-tmp"


def temp_workdir(prefix: str = ".sebastian-test-") -> Path:
    """创建一个测试临时目录，进程退出时兜底清理。"""
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix=prefix, dir=TMP_ROOT))
    atexit.register(shutil.rmtree, path, True)
    return path
