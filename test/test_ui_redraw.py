"""ui_redraw 单元测试：擦行重绘、半截输入、Markdown 行渲染、emit/token 缓冲。"""
import io
import threading
import unittest
from unittest.mock import patch

from src.utils import ui_redraw


class FakeReadline:
    def __init__(self, buffer):
        self.buffer = buffer

    def get_line_buffer(self):
        return self.buffer


class TestUiRedraw(unittest.TestCase):
    def setUp(self):
        self._old_prompt = ui_redraw._active_prompt
        self._old_tokens = dict(ui_redraw._token_streams)
        ui_redraw._active_prompt = None
        ui_redraw._token_streams.clear()

    def tearDown(self):
        ui_redraw._active_prompt = self._old_prompt
        ui_redraw._token_streams.clear()
        ui_redraw._token_streams.update(self._old_tokens)

    def test_redraw_restores_prompt_and_partial_input(self):
        out = io.StringIO()
        ui_redraw._active_prompt = {
            "prompt": "PROMPT> ",
            "owner": threading.get_ident(),
            "hidden": False,
        }
        with patch.object(ui_redraw, "readline", FakeReadline("y")), patch("sys.stdout", out):
            ui_redraw._redraw("BACKGROUND LOG")
        self.assertEqual(out.getvalue(), "\r\x1b[2KBACKGROUND LOG\nPROMPT> y")

    def test_emit_from_other_thread_redraws(self):
        ui_redraw._active_prompt = {
            "prompt": "P> ",
            "owner": -1,
            "hidden": False,
        }
        with patch.object(ui_redraw, "_redraw") as redraw:
            ui_redraw.emit("LOG")
        redraw.assert_called_once_with("LOG", nl=True)

    def test_gated_input_sets_and_clears_prompt_state(self):
        seen = {}

        def fake_input(prompt):
            seen["prompt"] = prompt
            seen["state"] = ui_redraw._active_prompt
            return "y"

        with patch.object(ui_redraw, "_is_tty", return_value=True), \
                patch.object(ui_redraw, "_flush_token_buffers"), \
                patch.object(ui_redraw, "_ORIG_INPUT", side_effect=fake_input):
            self.assertEqual(ui_redraw.gated_input("P> "), "y")

        self.assertEqual(seen["prompt"], "P> ")
        self.assertIsNotNone(seen["state"])
        self.assertIsNone(ui_redraw._active_prompt)

    def test_prompt_is_registered_before_waiting(self):
        out = io.StringIO()
        seen = {}

        def fake_wait(timeout):
            seen["active"] = ui_redraw._active_prompt
            return True

        with patch.object(ui_redraw, "_is_tty", return_value=True), \
                patch.object(ui_redraw, "_flush_token_buffers"), \
                patch.object(ui_redraw, "_wait_readable", side_effect=fake_wait), \
                patch.object(ui_redraw, "_ORIG_INPUT", return_value="1"), \
                patch("sys.stdout", out):
            ui_redraw.gated_input("P> ", timeout=1)

        self.assertIsNotNone(seen["active"])
        self.assertIn("P> ", out.getvalue())

    def test_redraw_restores_full_header_block(self):
        out = io.StringIO()
        ui_redraw._active_prompt = {
            "prompt": "> ",
            "header": "Q?\n1) A\n2) B",
            "owner": threading.get_ident(),
            "hidden": False,
        }
        with patch.object(ui_redraw, "readline", FakeReadline("1")), patch("sys.stdout", out):
            ui_redraw._redraw("LOG")
        text = out.getvalue()
        self.assertIn("\r\x1b[2K", text)
        self.assertIn("\x1b[1A", text)
        self.assertIn("LOG\nQ?\n1) A\n2) B\n> 1", text)

    def test_gated_input_header_is_stored(self):
        seen = {}

        def fake_input(prompt):
            seen["prompt"] = prompt
            seen["header"] = ui_redraw._active_prompt.get("header")
            return "1"

        with patch.object(ui_redraw, "_is_tty", return_value=True), \
                patch.object(ui_redraw, "_ORIG_INPUT", side_effect=fake_input), \
                patch("sys.stdout", io.StringIO()):
            ui_redraw.gated_input("> ", header="Q?\n1) A")

        self.assertEqual(seen["prompt"], "")
        self.assertEqual(seen["header"], "Q?\n1) A")

    def test_markdown_line_formatting(self):
        self.assertEqual(ui_redraw._format_line("# Title"), "Title")
        self.assertEqual(ui_redraw._format_line("**bold**"), "bold")
        self.assertEqual(ui_redraw._format_line("- item"), "• item")
        self.assertEqual(ui_redraw._format_line("> quote"), "│ quote")

    def test_markdown_code_fence_is_not_parsed_as_heading(self):
        stream = ui_redraw.MarkdownStream("agent")
        with patch.object(ui_redraw, "emit") as emit:
            stream.feed("```python\n# not a heading\n```\n")
        values = [c.args[0] for c in emit.call_args_list]
        self.assertIn("# not a heading", values)
        self.assertNotIn("not a heading", values)

    def test_emit_token_buffers_until_newline(self):
        with patch.object(ui_redraw, "emit") as emit:
            ui_redraw.emit_token("agent", "hel")
            ui_redraw.emit_token("agent", "lo\nwor")
            emit.assert_called_once_with("hello", agent="agent", nl=True)
            ui_redraw.emit_token("agent", "ld\n")
        self.assertEqual(emit.call_args_list[-1].args[0], "world")

    def test_flush_tokens_outputs_partial_line(self):
        ui_redraw.emit_token("agent", "partial")
        with patch.object(ui_redraw, "_ORIG_ECHO") as echo:
            ui_redraw.flush_tokens()
        echo.assert_called_once_with("partial", nl=True)


if __name__ == "__main__":
    unittest.main()
