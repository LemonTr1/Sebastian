# 本文件测 CronSchedule 的纯逻辑：字段匹配/表达式匹配/校验，以及 Schedule/List/Cancel 的纯逻辑结果（用临时持久化路径与 mock 隔离，避免写入真实 home 目录）。
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from src.tools.toolkits import cron_schedule
from src.tools.toolkits.cron_schedule import CronSchedule, CronJob


class TestCronFieldMatch(unittest.TestCase):
    def setUp(self):
        self.sched = CronSchedule()

    def test_wildcard(self):
        self.assertTrue(self.sched._cron_field_matches("*", 0))
        self.assertTrue(self.sched._cron_field_matches("*", 59))

    def test_step(self):
        self.assertTrue(self.sched._cron_field_matches("*/5", 10))
        self.assertFalse(self.sched._cron_field_matches("*/5", 12))
        self.assertFalse(self.sched._cron_field_matches("*/0", 5))

    def test_list(self):
        self.assertTrue(self.sched._cron_field_matches("1,15,30", 15))
        self.assertFalse(self.sched._cron_field_matches("1,15,30", 16))

    def test_range(self):
        self.assertTrue(self.sched._cron_field_matches("1-5", 3))
        self.assertFalse(self.sched._cron_field_matches("1-5", 6))

    def test_literal(self):
        self.assertTrue(self.sched._cron_field_matches("7", 7))
        self.assertFalse(self.sched._cron_field_matches("7", 8))

    def test_cron_matches_full(self):
        dt = datetime(2026, 1, 15, 9, 30)
        self.assertTrue(self.sched.cron_matches("30 9 15 * *", dt))
        self.assertFalse(self.sched.cron_matches("30 9 16 * *", dt))

    def test_dom_and_dow_or_semantics(self):
        dt = datetime(2026, 1, 15, 0, 0)  # 周四，工作日(1-5)为真
        # DOM=15 且 DOW=*  -> 只看 DOM
        self.assertTrue(self.sched.cron_matches("0 0 15 * *", dt))
        # DOM=16 且 DOW=1-5 都非* -> 任一匹配即可,周四命中
        self.assertTrue(self.sched.cron_matches("0 0 16 * 1-5", dt))

    def test_cron_matches_rejects_bad_field_count(self):
        self.assertFalse(self.sched.cron_matches("* * *", datetime.now()))

    def test_dow_zero_is_sunday(self):
        # 2026-01-04 是周日, cron 的 dow 应为 0
        dt = datetime(2026, 1, 4, 0, 0)
        self.assertTrue(self.sched.cron_matches("0 0 * * 0", dt))
        self.assertFalse(self.sched.cron_matches("0 0 * * 1", dt))


class TestCronValidate(unittest.TestCase):
    def setUp(self):
        self.sched = CronSchedule()

    def test_valid_expr(self):
        self.assertIsNone(self.sched.validate_cron("*/5 * * * *"))

    def test_wrong_field_count(self):
        self.assertIn("Expected 5 fields", self.sched.validate_cron("*/5 * * *"))

    def test_out_of_bounds(self):
        err = self.sched.validate_cron("60 * * * *")
        self.assertIsNotNone(err)
        self.assertIn("minute", err)
        err = self.sched.validate_cron("* 24 * * *")
        self.assertIn("hour", err)
        err = self.sched.validate_cron("* * 32 * *")
        self.assertIn("day-of-month", err)
        err = self.sched.validate_cron("* * * 13 *")
        self.assertIn("month", err)
        err = self.sched.validate_cron("* * * * 7")
        self.assertIn("day-of-week", err)

    def test_invalid_step_and_range(self):
        err = self.sched.validate_cron("*/x * * * *")
        self.assertIsNotNone(err)
        self.assertIn("step", err)
        err = self.sched.validate_cron("* * 5-2 * *")
        self.assertIsNotNone(err)
        self.assertIn("range", err.lower())


class TestCronListCancelFlow(unittest.TestCase):
    def setUp(self):
        self.sched = CronSchedule()
        self._tmp = tempfile.TemporaryDirectory()
        self._tmp_durable = Path(self._tmp.name) / "jobs.json"
        self._logger = mock.patch.object(cron_schedule, "logger")
        self._echo = mock.patch.object(cron_schedule.typer, "echo")
        self._logger.start()
        self._echo.start()
        self.addCleanup(self._logger.stop)
        self.addCleanup(self._echo.stop)
        self.addCleanup(self._tmp.cleanup)

    def _patch_durable(self):
        return mock.patch.object(cron_schedule, "DURABLE_PATH", self._tmp_durable)

    def test_run_schedule_invalid_returns_failure(self):
        resp = self.sched.run_schedule_cron("not * * *", "p")
        self.assertFalse(json.loads(resp)["success"])

    def test_run_schedule_valid_nondurable(self):
        with self._patch_durable():
            resp = self.sched.run_schedule_cron("0 9 * * 1", "morning", durable=False)
        data = json.loads(resp)
        self.assertTrue(data["success"])
        self.assertIn("Scheduled", data["summary"])

    def test_schedule_job_invalid_returns_error_string(self):
        self.assertIsInstance(self.sched.schedule_job("bad * * *", "p"), str)

    def test_run_list_empty_returns_failure(self):
        data = json.loads(self.sched.run_list_crons())
        self.assertFalse(data["success"])
        self.assertIn("No existed", data["error"])

    def test_run_list_with_jobs(self):
        self.sched.scheduled_jobs["j1"] = CronJob(
            id="j1", cron="* * * * *", prompt="say hello world repeatedly", recurring=True, durable=True)
        self.sched.scheduled_jobs["j2"] = CronJob(
            id="j2", cron="0 0 * * *", prompt="x" * 100, recurring=False, durable=False)
        out = self.sched.run_list_crons()
        self.assertIn("j1", out)
        self.assertIn("[recurring, durable]", out)
        self.assertIn("[one-shot, session]", out)
        # 超长 prompt 被截断到 40 字符
        self.assertNotIn("x" * 41, out)

    def test_cancel_not_found_returns_failure(self):
        data = json.loads(self.sched.run_cancel_cron("missing"))
        self.assertFalse(data["success"])
        self.assertIn("not found", data["error"])

    def test_cancel_found_removes_and_succeeds(self):
        with self._patch_durable():
            job = self.sched.schedule_job("0 0 * * *", "p")
            self.assertIn(job.id, self.sched.scheduled_jobs)
            resp = json.loads(self.sched.run_cancel_cron(job.id))
        self.assertTrue(resp["success"])
        self.assertNotIn(job.id, self.sched.scheduled_jobs)

    def test_cancel_job_returns_none_unknown(self):
        self.assertIsNone(self.sched.cancel_job("nope"))


class TestCronDurablePersistence(unittest.TestCase):
    def setUp(self):
        self.sched = CronSchedule()
        self._tmp = tempfile.TemporaryDirectory()
        self._tmp_path = Path(self._tmp.name) / "jobs.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_save_load_roundtrip(self):
        with mock.patch.object(cron_schedule, "DURABLE_PATH", self._tmp_path), \
             mock.patch.object(cron_schedule, "logger"), \
             mock.patch.object(cron_schedule.typer, "echo"):
            self.sched.scheduled_jobs["k"] = CronJob(
                id="k", cron="1 2 3 4 5", prompt="p", recurring=True, durable=True)
            self.sched.save_durable_jobs()
            loaded = CronSchedule()
            loaded.load_durable_jobs()
            self.assertIn("k", loaded.scheduled_jobs)
            self.assertEqual(loaded.scheduled_jobs["k"].cron, "1 2 3 4 5")

    def test_load_skips_invalid_job(self):
        payload = json.dumps([
            {"id": "bad", "cron": "not a cron at all", "prompt": "p", "recurring": True, "durable": True},
            {"id": "good", "cron": "0 0 * * *", "prompt": "p", "recurring": True, "durable": True},
        ])
        self._tmp_path.write_text(payload)
        with mock.patch.object(cron_schedule, "DURABLE_PATH", self._tmp_path), \
             mock.patch.object(cron_schedule, "logger"), \
             mock.patch.object(cron_schedule.typer, "echo"):
            self.sched.load_durable_jobs()
        self.assertIn("good", self.sched.scheduled_jobs)
        self.assertNotIn("bad", self.sched.scheduled_jobs)


if __name__ == "__main__":
    unittest.main()