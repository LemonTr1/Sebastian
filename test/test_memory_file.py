import unittest
from pathlib import Path
from unittest.mock import patch

from src.utils.memory_system import MEMORY_DIR, MEMORY_INDEX, Memory


class TestMemoryFile(unittest.TestCase):
    def test_off_injects_nothing(self):
        mem = Memory.__new__(Memory)
        mem.IS_ALLOWED = False
        self.assertEqual(mem.instruction_block(), "")

    def test_on_mentions_index_and_dir(self):
        mem = Memory.__new__(Memory)
        mem.IS_ALLOWED = True
        with patch.object(mem, "ensure_dir"):
            block = mem.instruction_block()
        self.assertIn(str(MEMORY_INDEX), block)
        self.assertIn(str(MEMORY_DIR), block)
        self.assertIn("不要在每轮开始时读取", block)
        self.assertNotIn("处理用户请求之前，先用 read", block)

    def test_is_memory_path_covers_dir_when_on(self):
        mem = Memory.__new__(Memory)
        mem.IS_ALLOWED = False
        self.assertFalse(mem.is_memory_path(str(MEMORY_INDEX)))
        mem.IS_ALLOWED = True
        self.assertTrue(mem.is_memory_path(str(MEMORY_INDEX)))
        self.assertTrue(mem.is_memory_path(str(MEMORY_DIR / "prefs.md")))
        self.assertFalse(mem.is_memory_path(str(Path.home() / "other.md")))


if __name__ == "__main__":
    unittest.main()
