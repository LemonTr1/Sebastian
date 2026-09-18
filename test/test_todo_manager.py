# 本文件测试 TodoManager 的纯逻辑：任务计划校验（条数/行径/status）、规范化、取回、轮次提醒与上下文插入（源码不涉及 todo 文件读写，故聚焦内存状态）。
import unittest
from unittest import mock

from src.tools.toolkits.todo_manager import TodoManager, PLAN_REMINDER_INTERVAL


class TestTodoManagerUpdate(unittest.TestCase):
    def setUp(self):
        self.manager = TodoManager()

    def test_happy_path_normalizes_and_stores(self):
        resp = self.manager.update([
            {"content": "  Write tests ", "status": "In_Progress"},
            {"content": "Run them", "status": "completed"},
        ])
        data = self._parse(resp)
        self.assertTrue(data["success"])
        items = self.manager.state.items
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].content, "Write tests")  # 去空白
        self.assertEqual(items[0].status, "in_progress")   # 小写化
        self.assertEqual(items[1].status, "completed")
        self.assertEqual(self.manager.state.rounds_since_update, 0)

    def test_too_many_items_fails(self):
        items = [{"content": f"task{i}", "status": "pending"} for i in range(11)]
        data = self._parse(self.manager.update(items))
        self.assertFalse(data["success"])
        self.assertIn("Too many items", data["error"])

    def test_ten_items_allowed(self):
        items = [{"content": f"task{i}", "status": "pending"} for i in range(10)]
        data = self._parse(self.manager.update(items))
        self.assertTrue(data["success"])

    def test_empty_content_fails_with_index(self):
        data = self._parse(self.manager.update([
            {"content": "ok", "status": "pending"},
            {"content": "   ", "status": "pending"},
        ]))
        self.assertFalse(data["success"])
        self.assertIn("Item index:1", data["error"])

    def test_invalid_status_fails(self):
        data = self._parse(self.manager.update([
            {"content": "x", "status": "blocked"},
        ]))
        self.assertFalse(data["success"])
        self.assertIn("status参数", data["error"])

    def test_two_in_progress_fails(self):
        data = self._parse(self.manager.update([
            {"content": "a", "status": "in_progress"},
            {"content": "b", "status": "in_progress"},
        ]))
        self.assertFalse(data["success"])
        self.assertIn("Only one plan item", data["error"])

    def test_call_magic_and_reset(self):
        self.manager([{"content": "c", "status": "pending"}])  # __call__ 委托给 update
        self.assertEqual(len(self.manager.state.items), 1)
        self.manager.reset()
        self.assertEqual(self.manager.state.items, [])

    def test_missing_content_key_fails(self):
        data = self._parse(self.manager.update([{"status": "pending"}]))
        self.assertFalse(data["success"])
        self.assertIn("Item index:0", data["error"])

    def _parse(self, text):
        import json
        return json.loads(text)


class TestTodoManagerReadout(unittest.TestCase):
    def setUp(self):
        self.manager = TodoManager()

    def test_get_normalized_empty(self):
        self.assertEqual(
            self.manager.get_normalized(),
            "<SYSTEM_REMINDER>当前任务计划为空</SYSTEM_REMINDER>",
        )

    def test_get_normalized_with_items(self):
        self.manager.update([{"content": "a", "status": "pending"}])
        self.assertIn("a", self.manager.get_normalized())
        self.assertIn("pending", self.manager.get_normalized())

    def test_reminder_no_items(self):
        self.assertIsNone(self.manager.reminder())

    def test_reminder_not_enough_rounds(self):
        self.manager.update([{"content": "a", "status": "pending"}])
        self.manager.state.rounds_since_update = PLAN_REMINDER_INTERVAL - 1
        self.assertIsNone(self.manager.reminder())

    def test_reminder_fires_with_exceed_count(self):
        self.manager.update([{"content": "a", "status": "pending"}])
        self.manager.state.rounds_since_update = PLAN_REMINDER_INTERVAL + 2
        msg = self.manager.reminder()
        self.assertIsNotNone(msg)
        # exceed = rounds_since_update - INTERVAL + 1 = 4 - 2 + 1
        self.assertIn("3", msg)

    def test_insert_todo_empty_returns_same_context(self):
        ctx = [{"role": "user", "content": "hi"}]
        self.assertIs(self.manager.insert_todo_into_context(ctx), ctx)

    def test_insert_todo_appends_block(self):
        self.manager.update([{"content": "a", "status": "completed"}])
        ctx = [{"role": "user", "content": "hi"}]
        result = self.manager.insert_todo_into_context(ctx)
        self.assertEqual(len(result), 2)
        self.assertIn("<TODO>", result[1]["content"])
        self.assertIn("</TODO>", result[1]["content"])

    def test_render_calls_typer(self):
        self.manager.update([
            {"content": "done", "status": "completed"},
            {"content": "busy", "status": "in_progress"},
            {"content": "todo", "status": "pending"},
        ])
        with mock.patch("src.tools.toolkits.todo_manager.typer.echo") as echo:
            self.manager.render()
            calls = " ".join(str(c) for c in echo.call_args_list)
            self.assertIn("[✓]", calls)
            self.assertIn("[>]", calls)
            self.assertIn("[ ]", calls)

    def test_render_empty_is_noop(self):
        with mock.patch("src.tools.toolkits.todo_manager.typer.echo") as echo:
            self.manager.render()
            echo.assert_not_called()


if __name__ == "__main__":
    unittest.main()