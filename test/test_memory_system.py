# 测 memory_system 的开关读写、目录/索引初始化与 manifest 读取（隔离真实 ~/.sebastian）
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.utils import memory_system


class TestMemorySystem(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.settings = self.tmp / "settings.json"
        self.memory_dir = self.tmp / ".memory"
        self.index = self.memory_dir / "MEMORY.md"
        # 用临时目录替换 ~/.sebastian 相关路径，避免动到真实目录
        self.settings_patcher = patch.object(memory_system, "SETTINGS", self.settings)
        self.dir_patcher = patch.object(memory_system, "MEMORY_DIR", self.memory_dir)
        self.index_patcher = patch.object(memory_system, "MEMORY_INDEX", self.index)
        self.settings_patcher.start()
        self.dir_patcher.start()
        self.index_patcher.start()
        self.addCleanup(self.settings_patcher.stop)
        self.addCleanup(self.dir_patcher.stop)
        self.addCleanup(self.index_patcher.stop)

    def test_init_off_when_no_settings(self):
        mem = memory_system.Memory()
        self.assertFalse(mem.is_allowed())

    def test_init_reads_enabled_true(self):
        self.settings.write_text(json.dumps({"memory": {"enabled": True}}), encoding="utf-8")
        mem = memory_system.Memory()
        self.assertTrue(mem.is_allowed())

    def test_init_reads_enabled_false(self):
        self.settings.write_text(json.dumps({"memory": {"enabled": False}}), encoding="utf-8")
        mem = memory_system.Memory()
        self.assertFalse(mem.is_allowed())

    def test_init_ignores_malformed_json(self):
        self.settings.write_text("{ not valid json", encoding="utf-8")
        mem = memory_system.Memory()
        self.assertFalse(mem.is_allowed())

    def test_init_defaults_to_false_when_key_missing(self):
        self.settings.write_text(json.dumps({"other": 1}), encoding="utf-8")
        mem = memory_system.Memory()
        self.assertFalse(mem.is_allowed())

    def test_set_enabled_true_writes_settings_and_creates_dir(self):
        mem = memory_system.Memory()
        mem.set_enabled(True)
        self.assertTrue(mem.is_allowed())
        saved = json.loads(self.settings.read_text(encoding="utf-8"))
        self.assertTrue(saved["memory"]["enabled"])
        self.assertTrue(self.memory_dir.is_dir())
        self.assertTrue(self.index.is_file())

    def test_set_enabled_false_turns_off(self):
        mem = memory_system.Memory()
        mem.set_enabled(True)
        mem.set_enabled(False)
        self.assertFalse(mem.is_allowed())
        saved = json.loads(self.settings.read_text(encoding="utf-8"))
        self.assertFalse(saved["memory"]["enabled"])

    def test_set_enabled_preserves_existing_keys(self):
        self.settings.write_text(json.dumps({"agent": {"x": 1}}), encoding="utf-8")
        mem = memory_system.Memory()
        mem.set_enabled(True)
        saved = json.loads(self.settings.read_text(encoding="utf-8"))
        self.assertEqual(saved["agent"]["x"], 1)
        self.assertTrue(saved["memory"]["enabled"])

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