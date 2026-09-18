# 测 eval/harness 的 run_case 装配与判定汇总（mock 隔离 runner / checkers / 工具注册 / 临时目录）
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.eval import harness


class _FakeRunner:
    """替身 runner：run() 立即返回或抛异常/阻塞，携带 metrics/last_reply。"""

    def __init__(self, reply="", metrics=None, exc=None, block=None):
        self.reply = reply
        self.metrics = metrics or {
            "tool_rounds": 0,
            "tool_calls": 0,
            "llm_turns": 0,
            "tools_called": [],
        }
        self.exc = exc
        self.block = block
        self.last_reply = reply

    def run(self, _prompt, _max_turns):
        if self.block is not None:
            self.block.wait()
        if self.exc is not None:
            raise self.exc
        return self.reply


def _case(**over):
    base = {
        "id": "unit-a",
        "prompt": "hello world",
        "timeout_sec": 2,
        "max_turns": 10,
        "expect": [{"type": "file_equals", "path": "hi.txt", "text": "hi"}],
        "setup": [{"path": "pre.txt", "content": "x"}],
        "symlinks": [],
    }
    base.update(over)
    return base


class TestRunCase(unittest.TestCase):
    def setUp(self):
        # run_case 强制在 ~/.sebastian-eval-* 建目录，本机沙箱/测试环境不可写，
        # 这里把 mkdtemp 重定向到可写的临时目录，保持确定性
        self._root = tempfile.TemporaryDirectory(prefix="sh-harness-")
        self.root = Path(self._root.name)

    def tearDown(self):
        self._root.cleanup()

    def _fake_mkdtemp(self, *a, **k):
        d = self.root / f"work-{len(list(self.root.iterdir()))}"
        d.mkdir()
        return str(d)

    def _run(self, runner, check_result=None, api_key="k", keep=False, **case_over):
        patches = [
            patch.object(harness, "API_KEY", api_key),
            patch.object(harness, "get_tools_registry", return_value=object()),
            patch.object(harness.tempfile, "mkdtemp", side_effect=self._fake_mkdtemp),
        ]
        if check_result is not None:
            patches.append(patch.object(harness, "run_checkers", return_value=check_result))
        runner_mock = MagicMock()
        runner_mock.create_runner.return_value = runner
        patches.append(patch.object(harness, "AgentRunner", runner_mock))
        for p in patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in patches])
        return harness.run_case(_case(**case_over), keep=keep)

    def test_passing_case_aggregates_passed_checks(self):
        passes_checks = [{"ok": True, "type": "x"}]
        result = self._run(_FakeRunner(reply="done"), check_result=passes_checks)
        self.assertTrue(result["passed"])
        self.assertIsNone(result["error"])
        self.assertEqual(result["reply"], "done")
        self.assertEqual(result["checks"], passes_checks)

    def test_checker_failure_yields_unpassed(self):
        result = self._run(
            _FakeRunner(reply="done"),
            check_result=[{"ok": True}, {"ok": False}],
        )
        self.assertFalse(result["passed"])
        self.assertIsNone(result["error"])
        self.assertFalse(all(c["ok"] for c in result["checks"]))

    def test_setup_files_are_written_into_workdir(self):
        result = self._run(_FakeRunner(reply="done"), check_result=[{"ok": True}], keep=True)
        # keep=True 时 workdir 保留在磁盘，校验 setup 文件已写入
        workdir = Path(result["workdir"])
        try:
            pre = workdir / "pre.txt"
            self.assertTrue(pre.exists())
            self.assertEqual(pre.read_text(encoding="utf-8"), "x")
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
        self.assertTrue(result["passed"])

    def test_runner_exception_recorded_as_exit_ok_false(self):
        result = self._run(_FakeRunner(exc=ValueError("boom")))
        self.assertFalse(result["passed"])
        self.assertEqual(result["error"], "boom")
        self.assertEqual(result["checks"], [{"type": "exit_ok", "ok": False, "detail": "boom"}])

    def test_runner_timeout_records_timeout(self):
        gate = threading.Event()
        # 让 gate 在超时(1s)之后(1.5s)才就绪，否则 run_case 的 executor with-shutdown
        # 会因线程卡在 gate.wait() 而永久阻塞
        timer = threading.Timer(1.5, gate.set)
        timer.daemon = True
        timer.start()
        self.addCleanup(gate.set)
        result = self._run(_FakeRunner(block=gate), timeout_sec=1)
        self.assertFalse(result["passed"])
        self.assertIn("timeout", result["error"])

    def test_inefficient_when_passed_and_over_ref_rounds(self):
        metrics = {k: v for k, v in _FakeRunner().metrics.items()}
        metrics["tool_rounds"] = 5
        result = self._run(
            _FakeRunner(reply="done", metrics=metrics),
            check_result=[{"ok": True}],
            ref_tool_rounds=3,
        )
        self.assertTrue(result["passed"])
        self.assertTrue(result["inefficient"])

    def test_not_inefficient_when_failed(self):
        # 失败用例即使 tool_rounds 超参考值也不标记 inefficient
        metrics = {k: v for k, v in _FakeRunner().metrics.items()}
        metrics["tool_rounds"] = 5
        result = self._run(
            _FakeRunner(reply="done", metrics=metrics),
            check_result=[{"ok": False}],
            ref_tool_rounds=3,
        )
        self.assertFalse(result["passed"])
        self.assertFalse(result["inefficient"])

    def test_result_contains_expected_keys(self):
        result = self._run(_FakeRunner(reply="done"), check_result=[{"ok": True}])
        for key in (
            "id", "passed", "inefficient", "tool_rounds", "tool_calls",
            "llm_turns", "tools_called", "tokens", "latency_sec", "reply",
            "checks", "error", "workdir",
        ):
            self.assertIn(key, result)

    def test_missing_api_key_raises(self):
        # 显式清空 API key（避免 real env 的 DEEPSEEK_API_KEY 让测试真去跑 Agent）
        with patch.object(harness, "API_KEY", ""), self.assertRaises(RuntimeError):
            harness.run_case(_case())


if __name__ == "__main__":
    unittest.main()