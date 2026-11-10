# 本文件测 bash 工具的纯逻辑：沙箱结果/异常到 JSON 返回的映射（全部 mock，不真实执行任何沙箱命令）。
import json
import unittest
from unittest import mock

from src.tools.toolkits.bash import bash, TIMEOUT


class TestBashBranches(unittest.TestCase):
    def test_sandbox_success_mapping(self):
        with mock.patch("src.tools.toolkits.bash.create_sandbox") as Sandbox:
            Sandbox.return_value.run.return_value = {
                "success": True, "stdout": "out", "stderr": "", "returncode": 0}
            out = json.loads(bash("echo hi", "desc"))
        self.assertTrue(out["success"])
        self.assertEqual(out["stdout"], "out")
        self.assertEqual(out["returncode"], 0)
        # sandbox.run 收到 command
        Sandbox.return_value.run.assert_called_once_with("echo hi")

    def test_sandbox_failure_mapping(self):
        with mock.patch("src.tools.toolkits.bash.create_sandbox") as Sandbox:
            Sandbox.return_value.run.return_value = {
                "success": False, "stdout": "", "stderr": "boom", "returncode": 1}
            out = json.loads(bash("false", "desc"))
        self.assertFalse(out["success"])
        self.assertEqual(out["stderr"], "boom")
        self.assertEqual(out["returncode"], 1)

    def test_runtime_error_branch(self):
        with mock.patch("src.tools.toolkits.bash.create_sandbox",
                        side_effect=RuntimeError("bwrap 未安装")):
            out = json.loads(bash("echo hi", "desc"))
        self.assertFalse(out["success"])
        self.assertIn("沙箱无法使用", out["error"])

    def test_filenotfound_branch(self):
        with mock.patch("src.tools.toolkits.bash.create_sandbox",
                        side_effect=FileNotFoundError("no config")):
            out = json.loads(bash("echo hi", "desc"))
        self.assertFalse(out["success"])
        self.assertIn("沙箱配置文件加载失败", out["error"])

    def test_json_decode_error_branch(self):
        with mock.patch("src.tools.toolkits.bash.create_sandbox",
                        side_effect=json.JSONDecodeError("bad", "doc", 0)):
            out = json.loads(bash("echo hi", "desc"))
        self.assertFalse(out["success"])
        self.assertIn("沙箱配置文件解析失败", out["error"])

    def test_generic_exception_branch(self):
        with mock.patch("src.tools.toolkits.bash.create_sandbox",
                        side_effect=ValueError("boom")):
            out = json.loads(bash("echo hi", "desc"))
        self.assertFalse(out["success"])
        self.assertIn("沙箱初始化失败", out["error"])

    def test_run_in_background_flag_accepted(self):
        # run_in_background 目前仅存在函数签名/flag 分支入口，验证其可被接受且不破坏正常路径
        with mock.patch("src.tools.toolkits.bash.create_sandbox") as Sandbox:
            Sandbox.return_value.run.return_value = {
                "success": True, "stdout": "", "stderr": "", "returncode": 0}
            out = json.loads(bash("sleep 1", "desc", run_in_background=True))
        self.assertTrue(out["success"])


class TestBashConstants(unittest.TestCase):
    def test_timeout_constant_defined(self):
        self.assertIsInstance(TIMEOUT, int)
        self.assertGreater(TIMEOUT, 0)


if __name__ == "__main__":
    unittest.main()
