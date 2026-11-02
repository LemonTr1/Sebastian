# 测 memory_system 的目录/索引初始化与 manifest 读取（记忆常开，无开关）
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.utils import memory_system


class TestMemorySystem(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.memory_dir = self.tmp / ".memory"
        self.index = self.memory_dir / "MEMORY.md"
        # 用临时目录替换 ~/.sebastian 相关路径，避免动到真实目录
        self.dir_patcher = patch.object(memory_system, "MEMORY_DIR", self.memory_dir)
        self.index_patcher = patch.object(memory_system, "MEMORY_INDEX", self.index)
        self.dir_patcher.start()
        self.index_patcher.start()
        self.addCleanup(self.dir_patcher.stop)
        self.addCleanup(self.index_patcher.stop)

    def test_memory_always_enabled(self):
        mem = memory_system.Memory()
        self.assertTrue(mem.is_memory_path(str(self.index)))
        self.assertTrue(mem.is_memory_path(str(self.memory_dir / "prefs.md")))
        self.assertFalse(mem.is_memory_path(None))
        self.assertFalse(mem.is_memory_path(""))

    def test_instruction_block_mentions_index_and_dir(self):
        mem = memory_system.Memory()
        block = mem.instruction_block()
        self.assertIn(str(self.index), block)
        self.assertIn(str(self.memory_dir), block)
        self.assertIn("不要在每轮开始时读取", block)
        self.assertTrue(self.memory_dir.is_dir())
        self.assertTrue(self.index.is_file())

    def test_ensure_dir_writes_index_template_once(self):
        mem = memory_system.Memory()
        mem.ensure_dir()
        self.assertTrue(self.index.is_file())
        content = self.index.read_text(encoding="utf-8")
        self.assertTrue(content.startswith("# Memory index"))
        # 再次调用不覆盖
        mem.ensure_dir()
        self.assertEqual(self.index.read_text(encoding="utf-8"), content)

    def test_manifest_index_returns_content_after_template(self):
        mem = memory_system.Memory()
        mem.ensure_dir()
        with open(str(self.index), "a", encoding="utf-8") as f:
            f.write("- [prefs](prefs.md) - 用户偏好\n")
        manifest = mem.manifest_index()
        self.assertIsNotNone(manifest)
        self.assertIn("prefs", manifest)
        self.assertNotIn("# Memory index", manifest)  # 模板部分被剥离

    def test_manifest_index_none_when_missing(self):
        mem = memory_system.Memory()
        self.assertIsNone(mem.manifest_index())


if __name__ == "__main__":
    unittest.main()
