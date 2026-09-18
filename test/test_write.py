# 该文件测试 write 工具：写新文件、覆盖已有文件、中文内容、非法路径/格式被拒。
import json
import tempfile
import unittest
from pathlib import Path

from src.tools.toolkits.write import write


class TestWrite(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix=".sebastian-test-", dir=str(Path(__file__).resolve().parents[1]))
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_write_new_file(self):
        p = self.dir / "new.txt"
        r = json.loads(write(str(p), "hello"))
        self.assertTrue(r["success"])
        self.assertEqual(p.read_text(encoding="utf-8"), "hello")

    def test_write_overwrites_existing(self):
        p = self.dir / "new.txt"
        p.write_text("old", encoding="utf-8")
        r = json.loads(write(str(p), "new content"))
        self.assertTrue(r["success"])
        self.assertEqual(p.read_text(encoding="utf-8"), "new content")

    def test_write_chinese_content(self):
        p = self.dir / "cn.txt"
        r = json.loads(write(str(p), "你好世界，测试写入。"))
        self.assertTrue(r["success"])
        self.assertEqual(p.read_text(encoding="utf-8"), "你好世界，测试写入。")

    def test_write_pdf_rejected(self):
        r = json.loads(write(str(self.dir / "a.pdf"), "x"))
        self.assertFalse(r["success"])
        self.assertIn("不支持写PDF", r.get("error", ""))

    def test_write_into_nonexistent_parent_fails(self):
        p = self.dir / "nope" / "sub.txt"
        r = json.loads(write(str(p), "x"))
        self.assertFalse(r["success"])


if __name__ == "__main__":
    unittest.main()