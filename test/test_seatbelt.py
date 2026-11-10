"""测试 src/sandbox/seatbelt.py：SBPL 配置生成、命令构造与结果映射（全部 mock，不依赖真实 macOS）。"""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# 隔离真实 ~/.sebastian：先设 HOME 再导入模块
_TMP_HOME = tempfile.mkdtemp(prefix="seb-seatbelt-test-")
os.environ["HOME"] = _TMP_HOME

from src.sandbox import seatbelt
from src.sandbox.seatbelt import SeatbeltSandbox


def _make_sb(config: dict | None = None) -> SeatbeltSandbox:
    """构造实例：跳过后端检测并注入受控 config。"""
    with mock.patch.object(SeatbeltSandbox, "_check_available", lambda self: None):
        with mock.patch.object(SeatbeltSandbox, "_load_config", return_value=config or {}):
            return SeatbeltSandbox()


class TestBuildProfile(unittest.TestCase):
    """_build_profile 按配置生成 deny_read / read_only / 网络规则。"""

    def setUp(self):
        self.home = Path(_TMP_HOME)
        self.ssh = self.home / ".ssh"
        self.ssh.mkdir(exist_ok=True)
        (self.ssh / "id_rsa").write_text("x", encoding="utf-8")
        self.netrc = self.home / ".netrc"
        self.netrc.write_text("x", encoding="utf-8")
        self.zshrc = self.home / ".zshrc"
        self.zshrc.write_text("x", encoding="utf-8")

    def test_deny_read_generates_read_and_write_denies(self):
        sb = _make_sb({"deny_read": ["~/.ssh", "~/.netrc"]})
        profile = sb._build_profile()
        self.assertIn(f'(deny file-read* (subpath "{self.ssh.resolve()}"))', profile)
        self.assertIn(f'(deny file-write* (subpath "{self.ssh.resolve()}"))', profile)
        self.assertIn(f'(deny file-read* (literal "{self.netrc.resolve()}"))', profile)

    def test_read_only_denies_write_only(self):
        sb = _make_sb({"read_only": ["~/.zshrc"]})
        profile = sb._build_profile()
        self.assertIn(f'(deny file-write* (literal "{self.zshrc.resolve()}"))', profile)
        self.assertNotIn(f'(deny file-read* (literal "{self.zshrc.resolve()}"))', profile)

    def test_missing_paths_are_skipped(self):
        sb = _make_sb({"deny_read": ["~/.does-not-exist"]})
        self.assertNotIn(".does-not-exist", sb._build_profile())

    def test_network_denied_when_unshare_net_true(self):
        sb = _make_sb({"unshare_net": True})
        self.assertIn("(deny network*)", sb._build_profile())

    def test_network_allowed_when_unshare_net_false(self):
        sb = _make_sb({"unshare_net": False})
        self.assertNotIn("(deny network*)", sb._build_profile())

    def test_home_is_writable_and_default_denies_writes(self):
        sb = _make_sb({})
        profile = sb._build_profile()
        self.assertIn("(allow default)", profile)
        self.assertIn("(deny file-write*)", profile)
        self.assertIn(f'(subpath "{seatbelt.HOME}")', profile)


class TestRunLogic(unittest.TestCase):
    """run() 的命令构造/超时取值/结果映射，全部 mock 掉真实 subprocess。"""

    def test_enabled_builds_sandbox_exec_command(self):
        sb = _make_sb({"enabled": True, "unshare_net": False})
        result = mock.Mock(returncode=0, stdout="ok", stderr="")
        with mock.patch("subprocess.run", return_value=result) as run:
            out = sb.run("echo hi", timeout=60)

        self.assertTrue(out["success"])
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[0], "sandbox-exec")
        self.assertEqual(cmd[1], "-p")
        self.assertEqual(cmd[3:], ["/bin/bash", "-c", "echo hi"])
        self.assertEqual(run.call_args.kwargs["cwd"], str(seatbelt.HOME))

    def test_disabled_uses_shell_directly(self):
        sb = _make_sb({"enabled": False})
        SeatbeltSandbox._disabled_warned = False
        result = mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch("subprocess.run", return_value=result) as run:
            sb.run("echo hi", timeout=60)
        self.assertEqual(run.call_args.args[0], ["/bin/bash", "-c", "echo hi"])

    def test_timeout_read_from_config(self):
        sb = _make_sb({"timeout": 9, "enabled": True})
        result = mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch("subprocess.run", return_value=result) as run:
            sb.run("echo", timeout=180)  # 调用方默认 180 应被配置 9 覆盖
        self.assertEqual(run.call_args.kwargs["timeout"], 9)

    def test_timeout_expired_returns_error(self):
        sb = _make_sb({"timeout": 3})
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("x", 1)):
            out = sb.run("echo", timeout=3)
        self.assertFalse(out["success"])
        self.assertEqual(out["returncode"], -1)
        self.assertIn("超时", out["stderr"])

    def test_generic_exception_returns_error(self):
        sb = _make_sb({})
        with mock.patch("subprocess.run", side_effect=OSError("boom")):
            out = sb.run("echo", timeout=3)
        self.assertFalse(out["success"])
        self.assertEqual(out["returncode"], -1)
        self.assertIn("boom", out["stderr"])


class TestCheckAvailable(unittest.TestCase):
    def test_raises_without_sandbox_exec(self):
        with mock.patch("src.sandbox.seatbelt.shutil.which", return_value=None):
            with self.assertRaises(RuntimeError):
                SeatbeltSandbox()


if __name__ == "__main__":
    unittest.main()
