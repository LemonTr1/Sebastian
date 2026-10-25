# 该文件测试 read 工具：读已有文件、不存在文件、offset/limit 边界、目录路径被拒、图片多模态读取、无后缀图片识别、大小上限。
import base64
import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import temp_workdir

from src.tools.toolkits.read import read, MAX_IMAGE_BYTES, MAX_TEXT_BYTES


class TestRead(unittest.TestCase):
    def setUp(self):
        self.dir = temp_workdir()
        self.f = self.dir / "data.txt"
        self.f.write_text("line1\nline2\nline3\nline4\n", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

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

    def test_uppercase_pdf_suffix_also_rejected(self):
        r = json.loads(read(str(self.dir / "REPORT.PDF")))
        self.assertFalse(r["success"])

    def test_offset_beyond_eof_returns_failure(self):
        r = json.loads(read(str(self.f), offset=99, limit=2))
        self.assertFalse(r["success"])
        self.assertIn("超出文件行数", r["summary"])

    def test_oversized_text_rejected(self):
        big = self.dir / "big.txt"
        with open(big, "wb") as f:
            f.seek(MAX_TEXT_BYTES)
            f.write(b"x")
        r = json.loads(read(str(big)))
        self.assertFalse(r["success"])
        self.assertIn("超过单次读取上限", r["summary"])

    def test_oversized_text_slice_still_works(self):
        big = self.dir / "big.txt"
        with open(big, "wb") as f:
            f.write(b"first\n" + b"x" * (MAX_TEXT_BYTES + 10))
        r = json.loads(read(str(big), offset=1, limit=1))
        self.assertTrue(r["success"])
        self.assertIn("first", r["content"])

    def test_uppercase_docx_suffix_also_rejected(self):
        r = json.loads(read(str(self.dir / "REPORT.DOCX")))
        self.assertFalse(r["success"])


class TestReadImage(unittest.TestCase):
    def setUp(self):
        self.dir = temp_workdir()
        self.png = self.dir / "a.png"
        self.png.write_bytes(b"\x89PNG fake data")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

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

    def test_read_extensionless_image_by_magic(self):
        # 无后缀图片（如截图临时文件）按文件头识别
        p = self.dir / "shot"
        p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"payload")
        r = read(str(p))
        self.assertTrue(r.get("__multimodal__"))
        self.assertEqual(r["parts"][1]["type"], "image_url")
        self.assertTrue(r["parts"][1]["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_read_extensionless_jpeg_by_magic(self):
        p = self.dir / "blob"
        p.write_bytes(b"\xff\xd8\xff\xe0" + b"payload")
        r = read(str(p))
        self.assertTrue(r.get("__multimodal__"))
        self.assertTrue(r["parts"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,"))

    def test_read_extensionless_text_still_text(self):
        p = self.dir / "notes"
        p.write_text("no extension but plain text", encoding="utf-8")
        r = json.loads(read(str(p)))
        self.assertTrue(r["success"])
        self.assertIn("no extension but plain text", r["content"])

    def test_read_text_starting_with_bm_not_treated_as_bmp(self):
        # "BM" 魔数只有两字节，纯文本不应被误判为 BMP
        p = self.dir / "b.txt"
        p.write_text("BMW is a car brand", encoding="utf-8")
        r = json.loads(read(str(p)))
        self.assertTrue(r["success"])
        self.assertIn("BMW", r["content"])


if __name__ == "__main__":
    unittest.main()