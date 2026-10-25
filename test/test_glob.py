import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import temp_workdir

from src.tools.toolkits.glob import glob


class TestGlob(unittest.TestCase):
    def setUp(self):
        self.workdir = temp_workdir()
        (self.workdir / "a.md").write_text("a", encoding="utf-8")
        (self.workdir / "b.txt").write_text("b", encoding="utf-8")
        nested = self.workdir / "sub"
        nested.mkdir()
        (nested / "c.md").write_text("c", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.workdir, ignore_errors=True)

    def test_glob_returns_relative_matches(self):
        result = json.loads(glob("*.md", str(self.workdir)))
        self.assertTrue(result["success"])
        self.assertEqual(sorted(result["content"]), ["a.md"])

    def test_glob_recursive(self):
        result = json.loads(glob("**/*.md", str(self.workdir)))
        self.assertTrue(result["success"])
        self.assertEqual(sorted(result["content"]), ["a.md", str(Path("sub") / "c.md")])


if __name__ == "__main__":
    unittest.main()
