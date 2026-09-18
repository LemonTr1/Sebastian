# 该文件测试 edit 工具：已有文本替换、old 不存在、多重匹配、replace_all、空 old/文档格式拒绝。
import json
import tempfile
import unittest
from pathlib import Path

from src.tools.toolkits.edit import edit


class TestEdit(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix=".sebastian-test-", dir=str(Path(__file__).resolve().parents[1]))
        self.dir = Path(self._tmp.name)
        self.f = self.dir / "doc.txt"

    def tearDown(self):
        self._tmp.cleanup()

    def test_edit_replaces_existing_text(self):
        self.f.write_text("hello world", encoding="utf-8")
        r = json.loads(edit(str(self.f), "world", "sebastian"))
        self.assertTrue(r["success"])
        self.assertEqual(self.f.read_text(encoding="utf-8"), "hello sebastian")

    def test_edit_old_not_found_fails(self):
        self.f.write_text("hello world", encoding="utf-8")
        r = json.loads(edit(str(self.f), "absent", "x"))
        self.assertFalse(r["success"])

    def test_edit_missing_file_fails(self):
        r = json.loads(edit(str(self.dir / "nope.txt"), "a", "b"))
        self.assertFalse(r["success"])

    def test_edit_empty_old_text_fails(self):
        self.f.write_text("hello", encoding="utf-8")
        r = json.loads(edit(str(self.f), "", "b"))
        self.assertFalse(r["success"])

    def test_edit_multiple_matches_requires_replace_all(self):
        self.f.write_text("a b a", encoding="utf-8")
        r = json.loads(edit(str(self.f), "a", "X"))
        self.assertFalse(r["success"])
        self.assertIn("多个匹配", r["summary"])

    def test_edit_replace_all(self):
        self.f.write_text("a b a", encoding="utf-8")
        r = json.loads(edit(str(self.f), "a", "X", replace_all=True))
        self.assertTrue(r["success"])
        self.assertEqual(self.f.read_text(encoding="utf-8"), "X b X")

    def test_edit_pdf_rejected(self):
        r = json.loads(edit(str(self.dir / "a.pdf"), "a", "b"))
        self.assertFalse(r["success"])
        self.assertIn("不支持编辑", r["summary"])


if __name__ == "__main__":
    unittest.main()