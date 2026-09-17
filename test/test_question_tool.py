"""question 工具单元测试：参数校验、降级分支、返回值映射（不真实弹窗）"""
import json
import unittest
from unittest.mock import patch

import src.tools.toolkits.question as q
from src.tools.tools_registry import get_tools_registry


class TestQuestionTool(unittest.TestCase):
    def setUp(self):
        # 默认让环境检查通过，避免测试机无 DISPLAY 时全部走降级分支
        for target, value in (
            ("is_dialog_available", (True, "")),
            ("is_eval_mode", False),
        ):
            patcher = patch.object(q, target, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_registered_and_not_hitl(self):
        registry = get_tools_registry()
        self.assertIsNotNone(registry.get_tool("question"))
        self.assertFalse(registry.is_hitl_tool("question"))
        self.assertIn("question", registry.agent_tools["Brain_Agent"])

    def test_empty_question_rejected(self):
        with patch.object(q._QUESTION_CLIENT, "ask") as ask:
            payload = json.loads(q.question("   "))
        self.assertFalse(payload["success"])
        self.assertEqual(payload["status"], "error")
        ask.assert_not_called()

    def test_too_many_options_rejected(self):
        options = [f"opt{i}" for i in range(q.MAX_OPTIONS + 1)]
        with patch.object(q._QUESTION_CLIENT, "ask") as ask:
            payload = json.loads(q.question("选一个", options))
        self.assertFalse(payload["success"])
        self.assertIn("选项过多", payload["error_message"])
        ask.assert_not_called()

    def test_options_json_string_accepted(self):
        with patch.object(q._QUESTION_CLIENT, "ask", return_value={
            "status": "answered", "answer": "B", "selected_option": "B", "is_free_text": False,
        }) as ask:
            q.question("选一个", '["A", "B"]')
        self.assertEqual(ask.call_args.kwargs["options"], ["A", "B"])

    def test_timeout_clamped(self):
        with patch.object(q._QUESTION_CLIENT, "ask", return_value={
            "status": "answered", "answer": "ok", "selected_option": None, "is_free_text": True,
        }) as ask:
            q.question("?", timeout=99999)
        self.assertEqual(ask.call_args.kwargs["timeout"], q.MAX_TIMEOUT)

    def test_answered_passthrough(self):
        with patch.object(q._QUESTION_CLIENT, "ask", return_value={
            "status": "answered", "answer": "PostgreSQL",
            "selected_option": "PostgreSQL", "is_free_text": False,
        }):
            payload = json.loads(q.question("用什么数据库？", ["PostgreSQL", "SQLite"]))
        self.assertTrue(payload["success"])
        self.assertEqual(payload["status"], "answered")
        self.assertEqual(payload["answer"], "PostgreSQL")
        self.assertFalse(payload["is_free_text"])

    def test_timeout_returns_hint(self):
        with patch.object(q._QUESTION_CLIENT, "ask", return_value={
            "status": "timeout", "answer": None, "selected_option": None, "is_free_text": False,
        }):
            payload = json.loads(q.question("?", timeout=5))
        self.assertFalse(payload["success"])
        self.assertEqual(payload["status"], "timeout")
        self.assertIn("hint", payload)
        self.assertIn("5", payload["error_message"])

    def test_unavailable_when_no_display(self):
        with patch.object(q, "is_dialog_available", return_value=(False, "no display")), \
                patch.object(q._QUESTION_CLIENT, "ask") as ask:
            payload = json.loads(q.question("?"))
        self.assertEqual(payload["status"], "unavailable")
        self.assertIn("hint", payload)
        ask.assert_not_called()

    def test_eval_mode_skips_dialog(self):
        with patch.object(q, "is_eval_mode", return_value=True), \
                patch.object(q._QUESTION_CLIENT, "ask") as ask:
            payload = json.loads(q.question("?"))
        self.assertEqual(payload["status"], "unavailable")
        ask.assert_not_called()


if __name__ == "__main__":
    unittest.main()