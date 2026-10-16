# 该文件测试 read 工具：读已有文件、不存在文件、offset/limit 边界、目录路径被拒、图片多模态读取。
import base64
import json
import tempfile
import unittest
from pathlib import Path

from src.tools.toolkits.read import read, MAX_IMAGE_BYTES


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


class TestReadImage(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix=".sebastian-test-", dir=str(Path(__file__).resolve().parents[1]))
        self.dir = Path(self._tmp.name)
        self.png = self.dir / "a.png"
        self.png.write_bytes(b"\x89PNG fake data")

    def tearDown(self):
        self._tmp.cleanup()

    def test_read_image_returns_multimodal(self):
        r = read(str(self.png))
        self.assertTrue(r.get("__multimodal__"))
        self.assertEqual(r["parts"][0]["type"], "text")
        self.assertEqual(r["parts"][1]["type"], "image_url")
        url = r["parts"][1]["image_url"]["url"]
        self.assertTrue(url.startswith("data:image/png;base64,"))
        self.assertEqual(base64.b64decode(url.split("base64,")[1]), b"\x89PNG fake data")

    def test_read_missing_image_rejected(self):
        r = json.loads(read(str(self.dir / "missing.png")))
        self.assertFalse(r["success"])
        self.assertIn("路径不存在", r["summary"])

    def test_read_oversized_image_rejected(self):
        big = self.dir / "big.png"
        big.write_bytes(b"\0" * (MAX_IMAGE_BYTES + 1))
        r = read(str(big))
        self.assertTrue(r.get("__multimodal__"))
        self.assertIn("图片过大", r["parts"][0]["text"])

    def test_read_non_image_extension_still_text(self):
        p = self.dir / "a.txt"
        p.write_text("plain text", encoding="utf-8")
        r = json.loads(read(str(p)))
        self.assertTrue(r["success"])
        self.assertIn("plain text", r["content"])


if __name__ == "__main__":
    unittest.main()