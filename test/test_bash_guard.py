# 本文件测 bash 工具的纯逻辑：命令守卫拦截、BubblewrapSandbox 结果/异常到 JSON 返回的映射（全部 mock，不真实执行任何沙箱命令）。
import json
import unittest
from unittest import mock

from src.security.command_guard import SecurityException
from src.tools.toolkits.bash import bash, TIMEOUT


class TestBashBranches(unittest.TestCase):
    def test_security_guard_blocks(self):
        with mock.patch("src.tools.toolkits.bash.security_guard",
                        side_effect=SecurityException("高危操作被系统拦截")):
            out = json.loads(bash("rm -rf /", "desc"))
        self.assertFalse(out["success"])
        self.assertIn("高危操作", out["error"])
        self.assertIn("高危操作", out["stderr"])

    def test_sandbox_success_mapping(self):
        with mock.patch("src.tools.toolkits.bash.security_guard") as guard:
            with mock.patch("src.tools.toolkits.bash.BubblewrapSandbox") as Sandbox:
                Sandbox.return_value.run.return_value = {
                    "success": True, "stdout": "out", "stderr": "", "returncode": 0}
                out = json.loads(bash("echo hi", "desc"))
        self.assertTrue(out["success"])
        self.assertEqual(out["stdout"], "out")
        self.assertEqual(out["returncode"], 0)
        guard.assert_called_once_with("echo hi")
        # sandbox.run 收到 command 与默认 timeout
        Sandbox.return_value.run.assert_called_once()

    def test_sandbox_failure_mapping(self):
        with mock.patch("src.tools.toolkits.bash.security_guard"):
            with mock.patch("src.tools.toolkits.bash.BubblewrapSandbox") as Sandbox:
                Sandbox.return_value.run.return_value = {
                    "success": False, "stdout": "", "stderr": "boom", "returncode": 1}
                out = json.loads(bash("false", "desc"))
        self.assertFalse(out["success"])
        self.assertEqual(out["stderr"], "boom")
        self.assertEqual(out["returncode"], 1)

    def test_runtime_error_branch(self):
        with mock.patch("src.tools.toolkits.bash.security_guard"):
            with mock.patch("src.tools.toolkits.bash.BubblewrapSandbox",
                            side_effect=RuntimeError("bwrap 未安装")):
                out = json.loads(bash("echo hi", "desc"))
        self.assertFalse(out["success"])
        self.assertIn("bubblewrap无法使用", out["error"])

    def test_filenotfound_branch(self):
        with mock.patch("src.tools.toolkits.bash.security_guard"):
            with mock.patch("src.tools.toolkits.bash.BubblewrapSandbox",
                            side_effect=FileNotFoundError("no config")):
                out = json.loads(bash("echo hi", "desc"))
        self.assertFalse(out["success"])
        self.assertIn("沙箱配置文件加载失败", out["error"])

    def test_json_decode_error_branch(self):
        with mock.patch("src.tools.toolkits.bash.security_guard"):
            with mock.patch("src.tools.toolkits.bash.BubblewrapSandbox",
                            side_effect=json.JSONDecodeError("bad", "doc", 0)):
                out = json.loads(bash("echo hi", "desc"))
        self.assertFalse(out["success"])
        self.assertIn("沙箱配置文件解析失败", out["error"])

    def test_generic_exception_branch(self):
        with mock.patch("src.tools.toolkits.bash.security_guard"):
            with mock.patch("src.tools.toolkits.bash.BubblewrapSandbox",
                            side_effect=ValueError("boom")):
                out = json.loads(bash("echo hi", "desc"))
        self.assertFalse(out["success"])
        self.assertIn("沙箱初始化失败", out["error"])

    def test_run_in_background_flag_accepted(self):
        # run_in_background 目前仅存在函数签名/flag 分支入口，验证其可被接受且不破坏正常路径
        with mock.patch("src.tools.toolkits.bash.security_guard"):
            with mock.patch("src.tools.toolkits.bash.BubblewrapSandbox") as Sandbox:
                Sandbox.return_value.run.return_value = {
                    "success": True, "stdout": "", "stderr": "", "returncode": 0}
                out = json.loads(bash("sleep 1", "desc", run_in_background=True))
        self.assertTrue(out["success"])


class TestBashGuardAgainstRealSideEffect(unittest.TestCase):
    def test_guard_blocks_known_danger(self):
        # 直接复用命令守卫，确认在真实 security_guard 下危险命令同样在 sandbox 前被拦下
        with mock.patch("src.tools.toolkits.bash.BubblewrapSandbox") as Sandbox:
            out = json.loads(bash("rm -rf /", "desc"))
        Sandbox.assert_not_called()  # 危险命令不应到达沙箱
        self.assertFalse(out["success"])

    def test_timeout_constant_defined(self):
        self.assertIsInstance(TIMEOUT, int)
        self.assertGreater(TIMEOUT, 0)


if __name__ == "__main__":
    unittest.main()