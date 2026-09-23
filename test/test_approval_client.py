"""ApprovalClient 测试：GUI 可用走子进程，不可用/无结果降级终端确认（不真实弹窗）"""
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from src.utils.approval_client import ApprovalClient


class FakePopen:
    """不写结果文件的假弹窗进程"""

    def __init__(self, cmd, **kwargs):
        self.cmd = cmd
        self.killed = False
        req = json.loads(Path(cmd[2]).read_text(encoding="utf-8"))
        self.result_file = Path(req["result_file"])

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self.killed = True


class FakePopenApproved(FakePopen):
    def wait(self, timeout=None):
        self.result_file.write_text(json.dumps({"approved": True}), encoding="utf-8")
        return 0


class TestApprovalClient(unittest.TestCase):
    def setUp(self):
        self.client = ApprovalClient(theme="dark")

    def test_gui_unavailable_uses_terminal(self):
        with patch("src.utils.approval_client.gui_available", return_value=(False, "no display")), \
                patch("src.utils.approval_client.terminal_confirm", return_value=True) as confirm:
            self.assertTrue(self.client.ask("bash", {"command": "ls"}))
        confirm.assert_called_once()

    def test_gui_available_approved(self):
        with patch("src.utils.approval_client.gui_available", return_value=(True, "")), \
                patch("src.utils.approval_client.subprocess.Popen", FakePopenApproved):
            self.assertTrue(self.client.ask("bash", {"command": "ls"}))

    def test_gui_available_denied(self):
        with patch("src.utils.approval_client.gui_available", return_value=(True, "")), \
                patch("src.utils.approval_client.subprocess.Popen", FakePopen):
            self.assertFalse(self.client.ask("bash", {"command": "ls"}))

    def test_gui_no_result_falls_back_to_terminal(self):
        with patch("src.utils.approval_client.gui_available", return_value=(True, "")), \
                patch("src.utils.approval_client.subprocess.Popen", FakePopen), \
                patch("src.utils.approval_client.terminal_ok", return_value=True), \
                patch("src.utils.approval_client.terminal_confirm", return_value=True) as confirm:
            self.assertTrue(self.client.ask("bash", {"command": "ls"}))
        confirm.assert_called_once()

    def test_gui_no_result_no_tty_denies(self):
        with patch("src.utils.approval_client.gui_available", return_value=(True, "")), \
                patch("src.utils.approval_client.subprocess.Popen", FakePopen), \
                patch("src.utils.approval_client.terminal_ok", return_value=False):
            self.assertFalse(self.client.ask("bash", {"command": "ls"}))


if __name__ == "__main__":
    unittest.main()
