"""interaction 模块测试：GUI 检测、终端审批/提问降级、ANSI 清洗"""
import io
import os
import unittest
from unittest.mock import patch

from src.utils import interaction
from src.utils.interaction import (
    gui_available,
    interaction_mode,
    sanitize,
    terminal_confirm,
    terminal_question,
)


class FakeStdin:
    def __init__(self, lines, tty=True):
        self._lines = list(lines)
        self._tty = tty

    def isatty(self):
        return self._tty

    def readline(self):
        if not self._lines:
            return ""  # EOF
        return self._lines.pop(0)


class FakeStdout(io.StringIO):
    def __init__(self, tty=True):
        super().__init__()
        self._tty = tty

    def isatty(self):
        return self._tty


class TestModeAndDetection(unittest.TestCase):
    def test_interaction_mode_default_and_invalid(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(interaction_mode(), "auto")
        with patch.dict(os.environ, {"SEBASTIAN_INTERACTION": "bogus"}, clear=True):
            self.assertEqual(interaction_mode(), "auto")
        with patch.dict(os.environ, {"SEBASTIAN_INTERACTION": "Terminal"}, clear=True):
            self.assertEqual(interaction_mode(), "terminal")

    def test_gui_forced_terminal(self):
        with patch.dict(os.environ, {"SEBASTIAN_INTERACTION": "terminal"}, clear=True):
            available, _ = gui_available()
        self.assertFalse(available)

    def test_gui_forced_gui(self):
        with patch.dict(os.environ, {"SEBASTIAN_INTERACTION": "gui"}, clear=True):
            available, _ = gui_available()
        self.assertTrue(available)

    def test_gui_auto_no_display(self):
        with patch.dict(
            os.environ,
            {"SEBASTIAN_INTERACTION": "auto", "DISPLAY": "", "WAYLAND_DISPLAY": ""},
            clear=True,
        ):
            available, reason = gui_available()
        self.assertFalse(available)
        self.assertIn("图形显示环境", reason)

    def test_gui_auto_missing_tkinter(self):
        with patch.dict(
            os.environ,
            {"SEBASTIAN_INTERACTION": "auto", "DISPLAY": ":0", "WAYLAND_DISPLAY": ""},
            clear=True,
        ), patch("src.utils.interaction.importlib.util.find_spec", return_value=None):
            available, reason = gui_available()
        self.assertFalse(available)
        self.assertIn("tkinter", reason)

    def test_gui_auto_available(self):
        with patch.dict(
            os.environ,
            {"SEBASTIAN_INTERACTION": "auto", "DISPLAY": ":0", "WAYLAND_DISPLAY": ""},
            clear=True,
        ), patch("src.utils.interaction.importlib.util.find_spec", return_value=object()):
            available, reason = gui_available()
        self.assertTrue(available)
        self.assertEqual(reason, "")


class TestSanitize(unittest.TestCase):
    def test_strips_ansi_and_control(self):
        self.assertEqual(sanitize("\x1b[31mred\x1b[0m\x07text"), "redtext")

    def test_keeps_newline_and_tab(self):
        self.assertEqual(sanitize("a\n\tb"), "a\n\tb")


class TestTerminalConfirm(unittest.TestCase):
    def _run(self, answer_lines, tool_args=None, timeout=None, tty=True):
        stdin = FakeStdin(answer_lines, tty=tty)
        stdout = FakeStdout(tty=tty)
        with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
            return terminal_confirm("bash", tool_args, timeout)

    def test_non_tty_denies(self):
        self.assertFalse(self._run([], tty=False))

    def test_yes(self):
        self.assertTrue(self._run(["y\n"]))

    def test_yes_long(self):
        self.assertTrue(self._run(["YES\n"]))

    def test_no(self):
        self.assertFalse(self._run(["n\n"]))

    def test_empty_defaults_deny(self):
        self.assertFalse(self._run(["\n"]))

    def test_eof_denies(self):
        self.assertFalse(self._run([]))

    def test_timeout_denies(self):
        stdin = FakeStdin(["y\n"])
        stdout = FakeStdout()
        with patch("sys.stdin", stdin), patch("sys.stdout", stdout), \
                patch("src.utils.interaction.select.select", return_value=([], [], [])):
            self.assertFalse(terminal_confirm("bash", {}, timeout=1))


class TestTerminalQuestion(unittest.TestCase):
    def _run(self, lines, options=None, timeout=None, tty=True):
        stdin = FakeStdin(lines, tty=tty)
        stdout = FakeStdout(tty=tty)
        with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
            return terminal_question("选一个", options, timeout)

    def test_non_tty_unavailable(self):
        res = self._run([], tty=False)
        self.assertEqual(res["status"], "unavailable")

    def test_select_option(self):
        res = self._run(["2\n"], options=["A", "B", "C"])
        self.assertEqual(res["status"], "answered")
        self.assertEqual(res["selected_option"], "B")
        self.assertFalse(res["is_free_text"])

    def test_free_text(self):
        res = self._run(["PostgreSQL\n"])
        self.assertEqual(res["status"], "answered")
        self.assertEqual(res["answer"], "PostgreSQL")
        self.assertTrue(res["is_free_text"])

    def test_invalid_number_then_valid(self):
        res = self._run(["9\n", "1\n"], options=["A", "B"])
        self.assertEqual(res["selected_option"], "A")

    def test_empty_then_valid(self):
        res = self._run(["\n", "2\n"], options=["A", "B"])
        self.assertEqual(res["selected_option"], "B")

    def test_eof_cancels(self):
        res = self._run([])
        self.assertEqual(res["status"], "cancelled")

    def test_timeout(self):
        stdin = FakeStdin(["x\n"])
        stdout = FakeStdout()
        with patch("sys.stdin", stdin), patch("sys.stdout", stdout), \
                patch("src.utils.interaction.select.select", return_value=([], [], [])):
            res = terminal_question("?", None, timeout=1)
        self.assertEqual(res["status"], "timeout")


class TestTerminalColor(unittest.TestCase):
    """无图形环境下的终端降级提示应着黄色，且仅在交互终端生效"""

    def _confirm_output(self, lines, tty=True, env=None):
        stdout = FakeStdout(tty=tty)
        with patch("sys.stdin", FakeStdin(lines, tty=tty)), \
                patch("sys.stdout", stdout), \
                patch.dict(os.environ, env if env is not None else {}, clear=True):
            terminal_confirm("bash", {"cmd": "rm -rf /tmp/x"}, None)
        return stdout.getvalue()

    def test_confirm_prompt_is_yellow_on_tty(self):
        out = self._confirm_output(["y\n"])
        self.assertIn("\x1b[33m", out)
        self.assertIn("是否允许？", out)

    def test_confirm_no_color_when_no_color_env(self):
        self.assertNotIn("\x1b[33m", self._confirm_output(["y\n"], env={"NO_COLOR": "1"}))

    def test_confirm_no_color_when_term_dumb(self):
        self.assertNotIn("\x1b[33m", self._confirm_output(["y\n"], env={"TERM": "dumb"}))

    def test_confirm_no_color_on_non_tty(self):
        self.assertNotIn("\x1b[33m", self._confirm_output([], tty=False))

    def test_question_prompt_is_yellow_on_tty(self):
        stdout = FakeStdout(tty=True)
        with patch("sys.stdin", FakeStdin(["2\n"], tty=True)), \
                patch("sys.stdout", stdout), \
                patch.dict(os.environ, {}, clear=True):
            res = terminal_question("选一个", ["A", "B"], None)
        self.assertEqual(res["selected_option"], "B")
        self.assertIn("\x1b[33m", stdout.getvalue())

    def test_question_no_color_on_non_tty(self):
        stdout = FakeStdout(tty=False)
        with patch("sys.stdin", FakeStdin([], tty=False)), \
                patch("sys.stdout", stdout), \
                patch.dict(os.environ, {}, clear=True):
            res = terminal_question("?", ["A"], None)
        self.assertEqual(res["status"], "unavailable")
        self.assertNotIn("\x1b[33m", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
