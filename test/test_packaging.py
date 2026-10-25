# 该文件校验打包一致性：pyproject.toml 与 requirements.txt 依赖不漂移，运行时资源已声明 package-data。
import re
import unittest
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 没有 tomllib，跳过本文件
    tomllib = None

REPO_ROOT = Path(__file__).resolve().parents[1]


def _normalize(spec: str) -> str:
    name = re.split(r"[<>=!~\[; ]", spec.strip(), maxsplit=1)[0]
    return name.lower().replace("_", "-")


def _pyproject() -> dict:
    with open(REPO_ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)


def _requirements() -> set:
    names = set()
    for line in (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            names.add(_normalize(line))
    return names


@unittest.skipIf(tomllib is None, "需要 Python 3.11+ 的 tomllib")
class TestPackaging(unittest.TestCase):
    def test_dependencies_match_requirements(self):
        pyproject = {_normalize(dep) for dep in _pyproject()["project"]["dependencies"]}
        requirements = _requirements()
        self.assertEqual(
            pyproject - requirements,
            set(),
            "pyproject.toml 有依赖未写入 requirements.txt",
        )
        self.assertEqual(
            requirements - pyproject,
            set(),
            "requirements.txt 有依赖未写入 pyproject.toml",
        )

    def test_runtime_resources_declared(self):
        package_data = _pyproject()["tool"]["setuptools"]["package-data"]
        self.assertEqual(package_data["src"], ["settings.json"])
        self.assertEqual(package_data["src.agents"], ["subagents/*.md"])


if __name__ == "__main__":
    unittest.main()
