"""批量运行 test/ 下所有 test_*.py，任一文件失败则整体退出码非 0。"""
import subprocess
import sys
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent


def main() -> int:
    files = sorted(TEST_DIR.glob("test_*.py"))
    failed = []
    for path in files:
        print(f"\n===== {path.name} =====", flush=True)
        proc = subprocess.run([sys.executable, str(path)], cwd=str(TEST_DIR.parent))
        if proc.returncode != 0:
            failed.append(path.name)

    print(f"\n===== {len(files) - len(failed)} passed, {len(failed)} failed =====")
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
