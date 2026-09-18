# 测 load_prompt：按名读取提示词、缺失文件名返回失败提醒、构造时只扫描 .md
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.utils.load_prompt import PROMPT_LOADER, PromptLoader


class TestPromptLoader(unittest.TestCase):
    def _make_dir(self):
        tmp = tempfile.TemporaryDirectory()
        return tmp, Path(tmp.name)

    def test_load_existing_prompt(self):
        tmp, root = self._make_dir()
        self.addCleanup(tmp.cleanup)
        md = root / "bash.md"
        md.write_text("你是一个 bash 助手。", encoding="utf-8")
        # 重定向 prompts 目录到临时目录，避免依赖真实提示词内容
        with patch("src.utils.load_prompt.PROMPTS_DIR", root):
            loader = PromptLoader()
            self.assertEqual(loader.load_prompt("bash"), "你是一个 bash 助手。")

    def test_load_missing_prompt_returns_failure(self):
        tmp, root = self._make_dir()
        self.addCleanup(tmp.cleanup)
        with patch("src.utils.load_prompt.PROMPTS_DIR", root):
            loader = PromptLoader()
            result = loader.load_prompt("no-such-prompt")
            self.assertIn("prompt加载失败", result)

    def test_constructor_only_picks_md_files(self):
        tmp, root = self._make_dir()
        self.addCleanup(tmp.cleanup)
        (root / "a.md").write_text("A", encoding="utf-8")
        (root / "b.md").write_text("B", encoding="utf-8")
        (root / "c.txt").write_text("not md", encoding="utf-8")
        (root / "d.py").write_text("# no", encoding="utf-8")
        with patch("src.utils.load_prompt.PROMPTS_DIR", root):
            loader = PromptLoader()
            names = sorted(f.name for f in loader.prompt_file_list)
            self.assertEqual(names, ["a.md", "b.md"])

    def test_empty_dir_list_empty(self):
        tmp, root = self._make_dir()
        self.addCleanup(tmp.cleanup)
        with patch("src.utils.load_prompt.PROMPTS_DIR", root):
            loader = PromptLoader()
            self.assertEqual(loader.prompt_file_list, [])

    def test_prompt_loader_singleton(self):
        # 模块级单例可直接取用
        self.assertTrue(hasattr(PROMPT_LOADER, "prompt_file_list"))
        self.assertIsInstance(PROMPT_LOADER.prompt_file_list, list)


if __name__ == "__main__":
    unittest.main()