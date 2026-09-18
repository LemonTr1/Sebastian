# 本文件测 SkillRegistry 的纯逻辑：加载 SKILL.md 文档、frontmatter 解析、未知技能返回失败、清单索引排序（全部用临时目录，无副作用）。
import json
import tempfile
import unittest
from pathlib import Path

from src.tools.toolkits.skill_registry import SkillRegistry


def _write(p: Path, content: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


class TestSkillDiscovery(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _load(self):
        return SkillRegistry(self._dir)

    def test_empty_dir_no_skills(self):
        reg = self._load()
        self.assertEqual(reg.documents, {})
        self.assertEqual(reg.describe_available(), "(no skills available)")

    def test_dir_created_if_missing(self):
        missing = self._dir / "nested" / "skills"
        SkillRegistry(missing)
        self.assertTrue(missing.is_dir())

    def test_loads_skill_with_frontmatter(self):
        _write(self._dir / "algo" / "SKILL.md",
               "---\nname: algo\ndescription: Sorting algorithms\n---\n# body\nstep1")
        reg = self._load()
        self.assertIn("algo", reg.documents)
        doc = reg.documents["algo"]
        self.assertEqual(doc.manifest.name, "algo")
        self.assertEqual(doc.manifest.description, "Sorting algorithms")
        self.assertTrue(doc.body.startswith("# body"))

    def test_no_frontmatter_falls_back_to_dir_name_and_body_is_full_text(self):
        _write(self._dir / "plain" / "SKILL.md", "just some text body")
        reg = self._load()
        doc = reg.documents["plain"]
        self.assertEqual(doc.manifest.name, "plain")  # 无 frontmatter 用父目录名
        self.assertEqual(doc.manifest.description, "No description provided.")
        self.assertEqual(doc.body, "just some text body")

    def test_load_full_text_unknown_returns_error(self):
        _write(self._dir / "known" / "SKILL.md", "---\nname: known\n---\nbody")
        reg = self._load()
        out = reg.load_full_text("nope")
        self.assertIn("Error: Unknown skill", out)
        self.assertIn("'nope'", out)
        self.assertIn("known", out)  # 提示可用技能

    def test_load_full_text_known_wraps_in_skill(self):
        _write(self._dir / "known" / "SKILL.md",
               "---\nname: known\ndescription: d\n---\nline1\nline2")
        reg = self._load()
        out = reg.load_full_text("known")
        self.assertIn('<skill name="known">', out)
        self.assertIn("line1", out)
        self.assertIn("</skill>", out)


if __name__ == "__main__":
    unittest.main()