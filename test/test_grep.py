# 该文件测试 grep 工具：命中、无命中、默认大小写敏感、忽略大小写及不可用路径被拒。
import json
import tempfile
import unittest
from pathlib import Path

from src.tools.toolkits.grep import grep


class TestGrep(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix=".sebastian-test-", dir=str(Path(__file__).resolve().parents[1]))
        self.dir = Path(self._tmp.name)
        (self.dir / "a.txt").write_text("Hello World\nsecond line\n", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_grep_finds_match(self):
        r = json.loads(grep("World", str(self.dir)))
        self.assertTrue(r["success"])
        self.assertEqual(len(r["matches"]), 1)
        self.assertEqual(r["matches"][0]["line"], 1)
        self.assertIn("Hello World", r["matches"][0]["text"])

    def test_grep_no_match(self):
        r = json.loads(grep("zzznotthere", str(self.dir)))
        self.assertTrue(r["success"])
        self.assertEqual(r["matches"], [])

    def test_grep_case_sensitive_by_default(self):
        r = json.loads(grep("world", str(self.dir)))
        self.assertTrue(r["success"])
        self.assertEqual(r["matches"], [])

    def test_grep_case_insensitive(self):
        r = json.loads(grep("world", str(self.dir), case_sensitive=False))
        self.assertTrue(r["success"])
        self.assertEqual(len(r["matches"]), 1)

    def test_grep_missing_path_fails(self):
        r = json.loads(grep("x", str(self.dir / "nope")))
        self.assertFalse(r["success"])
        self.assertEqual(r["matches"], [])


if __name__ == "__main__":
    unittest.main()