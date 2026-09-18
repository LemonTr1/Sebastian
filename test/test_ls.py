# 该文件测试 ls 工具：列出目录内容、不存在目录/文件路径返回失败。
import json
import tempfile
import unittest
from pathlib import Path

from src.tools.toolkits.ls import ls


class TestLs(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix=".sebastian-test-", dir=str(Path(__file__).resolve().parents[1]))
        self.dir = Path(self._tmp.name)
        (self.dir / "a.txt").write_text("a", encoding="utf-8")
        (self.dir / "sub").mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def test_ls_lists_directory(self):
        r = json.loads(ls(str(self.dir)))
        self.assertTrue(r["success"])
        self.assertIn("a.txt", r["file_list"])
        self.assertIn("sub", r["file_list"])

    def test_ls_nonexistent_directory_fails(self):
        r = json.loads(ls(str(self.dir / "nope")))
        self.assertFalse(r["success"])
        self.assertEqual(r["file_list"], [])
        self.assertIsNotNone(r["error"])

    def test_ls_file_path_fails(self):
        p = self.dir / "a.txt"
        r = json.loads(ls(str(p)))
        self.assertFalse(r["success"])
        self.assertEqual(r["file_list"], [])
        self.assertIn("不是有效目录", r["error"])

    def test_ls_empty_directory(self):
        empty = self.dir / "empty"
        empty.mkdir()
        r = json.loads(ls(str(empty)))
        self.assertTrue(r["success"])
        self.assertEqual(r["file_list"], [])


if __name__ == "__main__":
    unittest.main()