# 该文件补充测试 glob 工具：无匹配、超 MAX_RESULTS 截断、安全问题拒绝，作为现有 test_glob.py 的补充。
import json
import tempfile
import unittest
from pathlib import Path

from src.tools.toolkits.glob import glob, MAX_RESULTS


class TestGlobExtra(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix=".sebastian-test-", dir=str(Path(__file__).resolve().parents[1]))
        self.dir = Path(self._tmp.name)
        (self.dir / "a.txt").write_text("a", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_glob_no_match(self):
        r = json.loads(glob("*.xyz", str(self.dir)))
        self.assertTrue(r["success"])
        self.assertEqual(r["content"], [])

    def test_glob_truncates_when_too_many(self):
        for i in range(MAX_RESULTS + 10):
            (self.dir / f"f{i}.md").write_text("x", encoding="utf-8")
        r = json.loads(glob("*.md", str(self.dir)))
        self.assertTrue(r["success"])
        self.assertEqual(len(r["content"]), MAX_RESULTS)
        self.assertIn("结果过多", r["summary"])

    def test_glob_relies_on_recursive(self):
        nested = self.dir / "sub"
        nested.mkdir()
        (nested / "deep.txt").write_text("x", encoding="utf-8")
        r = json.loads(glob("**/*.txt", str(self.dir)))
        self.assertTrue(r["success"])
        self.assertIn("sub/deep.txt", r["content"])

    def test_glob_unsafe_scope_rejected(self):
        # 家目录外 / 不存在的 scope 应在 resolve_safe_path 处被拒绝
        r = json.loads(glob("*.txt", "/nonexistent_sebastian_outside_home"))
        self.assertFalse(r["success"])
        self.assertIsNone(r["content"])


if __name__ == "__main__":
    unittest.main()