"""测试 src/sandbox/bubblewrap.py：配置两级回退、deny_read/read_only 解析、超时取值、参数构造（mock 隔离真实沙箱执行）。"""
import json
import tempfile
from pathlib import Path
from unittest import mock
import unittest
import os

# 隔离真实 ~/.sebastian：先设 HOME 再导入模块
_TMP_HOME = tempfile.mkdtemp(prefix="seb-bwrap-test-")
os.environ["HOME"] = _TMP_HOME

from src.sandbox import bubblewrap
from src.sandbox.bubblewrap import BubblewrapSandbox


def _make_sb(config: dict | None = None) -> BubblewrapSandbox:
    """构造实例：跳过真实 bwrap 检测并注入受控 config。"""
    with mock.patch.object(BubblewrapSandbox, "_check_bwrap", lambda self: None):
        with mock.patch.object(BubblewrapSandbox, "_load_config", return_value=config or {}):
            return BubblewrapSandbox()


class TestLoadConfig(unittest.TestCase):
    """_load_config 用户 settings → 项目默认 的两级回退，损坏配置不回退不抛异常。"""

    def _make(self, user_path, user_payload, default_path, default_payload):
        # 写入内存配置到对应路径；payload 为 None 表示该文件应缺失
        if user_payload is not None:
            user_path.write_text(json.dumps(user_payload), encoding="utf-8")
        default_path.write_text(json.dumps(default_payload), encoding="utf-8")
        with mock.patch.object(bubblewrap, "SETTINGS", user_path):
            with mock.patch.object(bubblewrap, "DEFAULT_SETTINGS", default_path):
                with mock.patch.object(BubblewrapSandbox, "_check_bwrap", lambda self: None):
                    return BubblewrapSandbox()

    def test_user_config_with_sandbox_section_wins(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            sb = self._make(d / "user.json", {"sandbox": {"timeout": 5}},
                            d / "default.json", {"sandbox": {"timeout": 999}})
        self.assertEqual(sb.config, {"timeout": 5})

    def test_user_config_without_sandbox_uses_whole_doc(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            sb = self._make(d / "user.json", {"timeout": 7},
                            d / "default.json", {"sandbox": {"timeout": 999}})
        self.assertEqual(sb.config, {"timeout": 7})

    def test_fallback_to_default_when_user_missing(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            sb = self._make(d / "missing-user.json", None,
                            d / "default.json", {"sandbox": {"timeout": 42}})
        self.assertEqual(sb.config.get("timeout"), 42)

    def test_fallback_to_default_when_user_json_corrupted(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            user = d / "corrupt.json"
            user.write_text("{ not valid json", encoding="utf-8")
            sb = self._make(user, None,
                            d / "default.json", {"sandbox": {"enabled": False}})
        self.assertFalse(sb.config.get("enabled"))

    def test_default_sandbox_is_used_as_final_backup(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            sb = self._make(d / "missing.json", None,
                            d / "default.json", {"sandbox": {"read_only": ["/etc"], "timeout": 10}})
        self.assertEqual(sb.config["read_only"], ["/etc"])


class TestMount(unittest.TestCase):
    """_mount 在三种模式下生成对应的 bwrap 参数。"""

    def setUp(self):
        self.sb = _make_sb()

    def test_read_only_binds_ro(self):
        args = []
        with mock.patch("os.path.exists", return_value=True):
            self.sb._mount(args, "/etc/foo", "read_only")
        self.assertIn("--ro-bind", args)

    def test_allow_write_binds_rw(self):
        args = []
        with mock.patch("os.path.exists", return_value=True):
            self.sb._mount(args, "/home/x", "allow_write")
        self.assertIn("--bind", args)

    def test_deny_read_dir_uses_tmpfs(self):
        args = []
        with mock.patch("os.path.isdir", return_value=True), mock.patch("os.path.exists", return_value=True):
            self.sb._mount(args, "/root/.ssh", "deny_read")
        self.assertIn("--tmpfs", args)

    def test_deny_read_file_maps_to_dev_null(self):
        args = []
        with mock.patch("os.path.isdir", return_value=False), mock.patch("os.path.exists", return_value=True):
            self.sb._mount(args, "/root/.netrc", "deny_read")
        self.assertEqual(args[:2], ["--ro-bind", "/dev/null"])
        self.assertTrue(args[-1].endswith(".netrc"))

    def test_missing_path_is_skipped(self):
        args = ["bwrap"]
        with mock.patch("os.path.exists", return_value=False):
            self.sb._mount(args, "/no/such/thing", "deny_read")
        self.assertEqual(args, ["bwrap"])


class TestRunLogic(unittest.TestCase):
    """run() 的命令构造/超时取值/结果映射，全部 mock 掉真实 subprocess。"""

    def test_enabled_builds_bwrap_command(self):
        sb = _make_sb({
            "enabled": True, "unshare_net": False,
            "read_only": ["/etc/ssl"], "deny_read": ["/root/.ssh"],
        })
        result = mock.Mock(returncode=0, stdout="ok", stderr="")
        with mock.patch("subprocess.run", return_value=result) as run:
            with mock.patch.object(sb, "_mount") as mount:
                out = sb.run("echo hi", timeout=60)

        self.assertTrue(out["success"])
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[0], "bwrap")
        self.assertNotIn("--unshare-net", cmd)
        self.assertEqual(cmd[-4:], ["--", "/bin/bash", "-c", "echo hi"])

        mount.assert_any_call(mock.ANY, "/etc/ssl", "read_only")
        mount.assert_any_call(mock.ANY, "/root/.ssh", "deny_read")

    def test_unshare_net_true_means_network_isolated(self):
        sb = _make_sb({"unshare_net": True, "enabled": True})
        result = mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch("subprocess.run", return_value=result) as run:
            with mock.patch.object(sb, "_mount"):
                sb.run("echo", timeout=60)
        self.assertIn("--unshare-net", run.call_args.args[0])

    def test_disabled_uses_shell_directly(self):
        sb = _make_sb({"enabled": False})
        result = mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch("subprocess.run", return_value=result) as run:
            with mock.patch.object(sb, "_mount"):
                sb.run("echo hi", timeout=60)
        cmd = run.call_args.args[0]
        self.assertEqual(cmd, ["/bin/bash", "-c", "echo hi"])

    def test_timeout_read_from_config(self):
        sb = _make_sb({"timeout": 9, "enabled": True})
        result = mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch("subprocess.run", return_value=result) as run:
            with mock.patch.object(sb, "_mount"):
                sb.run("echo", timeout=180)  # 调用方默认 180 应被配置 9 覆盖
        self.assertEqual(run.call_args.kwargs["timeout"], 9)

    def test_timeout_expired_returns_error(self):
        sb = _make_sb({"timeout": 3})
        with mock.patch("subprocess.run", side_effect=__import__("subprocess").TimeoutExpired("x", 1)):
            with mock.patch.object(sb, "_mount"):
                out = sb.run("echo", timeout=3)
        self.assertFalse(out["success"])
        self.assertEqual(out["returncode"], -1)
        self.assertIn("超时", out["stderr"])

    def test_generic_exception_returns_error(self):
        sb = _make_sb({})
        with mock.patch("subprocess.run", side_effect=OSError("boom")):
            with mock.patch.object(sb, "_mount"):
                out = sb.run("echo", timeout=3)
        self.assertFalse(out["success"])
        self.assertEqual(out["returncode"], -1)
        self.assertIn("boom", out["stderr"])


if __name__ == "__main__":
    unittest.main()