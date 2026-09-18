# 该文件测试 read 工具：读已有文件、不存在文件、offset/limit 边界、目录路径被拒。
import json
import tempfile
import unittest
from pathlib import Path

from src.tools.toolkits.read import read


class TestRead(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix=".sebastian-test-", dir=str(Path(__file__).resolve().parents[1]))
        self.dir = Path(self._tmp.name)
        self.f = self.dir / "data.txt"
        self.f.write_text("line1\nline2\nline3\nline4\n", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_read_existing_file(self):
        r = json.loads(read(str(self.f)))
        self.assertTrue(r["success"])
        self.assertIn("line1", r["content"])
        self.assertIn("line4", r["content"])

    def test_read_missing_file_returns_failure(self):
        r = json.loads(read(str(self.dir / "nope.txt")))
        self.assertFalse(r["success"])
        self.assertIsNone(r["content"])

    def test_read_directory_returns_failure(self):
        r = json.loads(read(str(self.dir)))
        self.assertFalse(r["success"])
        self.assertIsNone(r["content"])

    def test_offset_without_limit_fails(self):
        r = json.loads(read(str(self.f), offset=2))
        self.assertFalse(r["success"])
        self.assertIn("同时设置", r["error"])

    def test_limit_without_offset_fails(self):
        r = json.loads(read(str(self.f), limit=2))
        self.assertFalse(r["success"])

    def test_read_with_offset_limit(self):
        r = json.loads(read(str(self.f), offset=2, limit=2))
        self.assertTrue(r["success"])
        self.assertIn("2:  line2", r["content"])
        self.assertIn("3:  line3", r["content"])
        self.assertNotIn("1:  line1", r["content"])

    def test_nonpositive_offset_fails(self):
        r = json.loads(read(str(self.f), offset=0, limit=2))
        self.assertFalse(r["success"])

    def test_nonpositive_limit_fails(self):
        r = json.loads(read(str(self.f), offset=1, limit=0))
        self.assertFalse(r["success"])

    def test_read_pdf_returns_failure(self):
        r = json.loads(read(str(self.dir / "a.pdf")))
        self.assertFalse(r["success"])


if __name__ == "__main__":
    unittest.main()