# 该文件测试 view_image 工具：支持格式、大小与存在性校验，返回多模态 dict 或错误 dict。
import base64
import tempfile
import unittest
from pathlib import Path

from src.tools.toolkits.view_image import view_image, MAX_IMAGE_BYTES


class TestViewImage(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix=".sebastian-test-", dir=str(Path(__file__).resolve().parents[1]))
        self.dir = Path(self._tmp.name)
        self.png = self.dir / "a.png"
        self.png.write_bytes(b"\x89PNG fake data")

    def tearDown(self):
        self._tmp.cleanup()

    def test_view_supported_png(self):
        r = view_image(str(self.png))
        self.assertTrue(r.get("__multimodal__"))
        self.assertEqual(r["parts"][0]["type"], "text")
        self.assertEqual(r["parts"][1]["type"], "image_url")
        url = r["parts"][1]["image_url"]["url"]
        self.assertTrue(url.startswith("data:image/png;base64,"))
        self.assertEqual(base64.b64decode(url.split("base64,")[1]), b"\x89PNG fake data")

    def test_view_unsupported_extension_rejected(self):
        p = self.dir / "a.txt"
        p.write_text("x", encoding="utf-8")
        r = view_image(str(p))
        self.assertTrue(r.get("__multimodal__"))
        self.assertEqual(r["parts"][0]["type"], "text")
        self.assertIn("不支持的文件类型", r["parts"][0]["text"])

    def test_view_missing_file_rejected(self):
        r = view_image(str(self.dir / "missing.png"))
        self.assertTrue(r.get("__multimodal__"))
        self.assertIn("路径不存在", r["parts"][0]["text"])

    def test_view_oversized_image_rejected(self):
        big = self.dir / "big.png"
        big.write_bytes(b"\0" * (MAX_IMAGE_BYTES + 1))
        r = view_image(str(big))
        self.assertTrue(r.get("__multimodal__"))
        self.assertIn("图片过大", r["parts"][0]["text"])


if __name__ == "__main__":
    unittest.main()