import os
import tempfile
import unittest
from pathlib import Path

from src.eval.checkers import run_checkers
from src.eval.harness import load_cases
from src.utils.eval_flag import is_eval_mode


class TestEvalCheckers(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix=".sebastian-eval-test-", dir=str(Path.home()))
        self.workdir = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_file_equals_strips(self):
        (self.workdir / "hello.txt").write_text("Hello Sebastian\n", encoding="utf-8")
        results = run_checkers(
            self.workdir,
            [{"type": "file_equals", "path": "hello.txt", "text": "Hello Sebastian"}],
            {},
            "",
        )
        self.assertTrue(results[0]["ok"])

    def test_file_absent_absolute(self):
        results = run_checkers(
            self.workdir,
            [{"type": "file_absent", "path": "/tmp/sebastian-eval-pwn-does-not-exist.txt"}],
            {},
            "",
        )
        self.assertTrue(results[0]["ok"])

    def test_tool_called(self):
        metrics = {"tools_called": ["read", "write"], "tool_calls": 2}
        results = run_checkers(
            self.workdir,
            [
                {"type": "tool_called", "name": "write"},
                {"type": "tool_not_called", "name": "bash"},
                {"type": "tool_calls_eq", "value": 2},
            ],
            metrics,
            "",
        )
        self.assertTrue(all(r["ok"] for r in results))

    def test_assistant_contains(self):
        results = run_checkers(
            self.workdir,
            [{"type": "assistant_contains", "text": "6"}],
            {},
            "3! = 6",
        )
        self.assertTrue(results[0]["ok"])

    def test_only_files_rejects_extra(self):
        (self.workdir / "app.log").write_text("x", encoding="utf-8")
        (self.workdir / "error.txt").write_text("y", encoding="utf-8")
        (self.workdir / "dump.txt").write_text("z", encoding="utf-8")
        results = run_checkers(
            self.workdir,
            [{"type": "only_files", "files": ["app.log", "error.txt"]}],
            {},
            "",
        )
        self.assertFalse(results[0]["ok"])

    def test_only_files_ok(self):
        (self.workdir / "app.log").write_text("x", encoding="utf-8")
        (self.workdir / "error.txt").write_text("y", encoding="utf-8")
        results = run_checkers(
            self.workdir,
            [{"type": "only_files", "files": ["app.log", "error.txt"]}],
            {},
            "",
        )
        self.assertTrue(results[0]["ok"])


class TestEvalCases(unittest.TestCase):
    def test_offline_suite_has_twelve_plus_online(self):
        offline = load_cases(include_online=False)
        ids = {c["id"] for c in offline}
        self.assertIn("write_hello", ids)
        self.assertIn("deny_etc_passwd", ids)
        self.assertNotIn("web_search_one", ids)
        all_cases = load_cases(include_online=True)
        self.assertTrue(any(c["id"] == "web_search_one" for c in all_cases))

    def test_tag_security(self):
        cases = load_cases(tag="security")
        self.assertEqual({c["id"] for c in cases}, {
            "deny_etc_passwd",
            "deny_rm_rf",
            "deny_tmp_write",
            "symlink_leak",
            "poisoned_task",
        })

    def test_tag_hard(self):
        cases = load_cases(tag="hard")
        self.assertEqual(len(cases), 7)
        self.assertTrue(all("hard" in c["tags"] for c in cases))


class TestEvalFlag(unittest.TestCase):
    def test_eval_flag_reads_env(self):
        old = os.environ.get("SEBASTIAN_EVAL")
        try:
            os.environ.pop("SEBASTIAN_EVAL", None)
            self.assertFalse(is_eval_mode())
            os.environ["SEBASTIAN_EVAL"] = "1"
            self.assertTrue(is_eval_mode())
        finally:
            if old is None:
                os.environ.pop("SEBASTIAN_EVAL", None)
            else:
                os.environ["SEBASTIAN_EVAL"] = old


if __name__ == "__main__":
    unittest.main()
