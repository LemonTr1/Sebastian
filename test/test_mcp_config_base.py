"""测试 src/mcp/config.py：load_mcp_settings 两级回退、connect_timeout、get_server、load_servers 全局关闭与非法条目跳过（不含 env 展开，见 test_mcp_config_env.py）。"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# 先隔离真实 ~/.sebastian，避免读取/写日志到用户配置
_TMP_HOME = tempfile.mkdtemp(prefix="seb-mcpcfg-test-")
os.environ["HOME"] = _TMP_HOME

from src.mcp.config import (
    DEFAULT_CONNECT_TIMEOUT,
    McpServerConfig,
    load_mcp_settings,
    connect_timeout,
    get_server,
    load_servers,
)
from src.mcp import config as mcp_config


def _write(path: Path, payload) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="seb-mcpcfg-case-"))
        self.user = self.tmp / "user.json"
        self.default = self.tmp / "default.json"
        self._patch = mock.patch.multiple(
            mcp_config, SETTINGS=self.user, DEFAULT_SETTINGS=self.default
        )
        self._patch.start()
        self.addCleanup(self._patch.stop)

    def _mk(self, user=None, default=None):
        if user is not None:
            _write(self.user, user)
        if default is None:
            default = {"mcp": {"enabled": True, "servers": {}}}
        _write(self.default, default)


class TestLoadMcpSettings(_Base):
    def test_user_section_wins(self):
        self._mk(user={"mcp": {"connect_timeout": 9}},
                 default={"mcp": {"connect_timeout": 1}})
        self.assertEqual(load_mcp_settings()["connect_timeout"], 9)

    def test_fallback_to_default_when_user_absent(self):
        self._mk(default={"mcp": {"connect_timeout": 7}})
        self.assertEqual(load_mcp_settings()["connect_timeout"], 7)

    def test_empty_when_both_absent(self):
        self._mk(default={"mcp": {"connect_timeout": 5}})
        self.default.unlink()
        self.assertEqual(load_mcp_settings(), {})

    def test_mcp_section_missing_in_user_uses_default(self):
        # 用户文件存在但无 mcp 段
        self._mk(user={"sandbox": {}}, default={"mcp": {"connect_timeout": 3}})
        self.assertEqual(load_mcp_settings()["connect_timeout"], 3)


class TestConnectTimeout(_Base):
    def test_default_when_missing(self):
        self._mk(default={"mcp": {}})
        self.assertEqual(connect_timeout(), DEFAULT_CONNECT_TIMEOUT)

    def test_from_config(self):
        self._mk(user={"mcp": {"connect_timeout": 15.5}})
        self.assertEqual(connect_timeout(), 15.5)

    def test_invalid_string_falls_back(self):
        self._mk(user={"mcp": {"connect_timeout": "abc"}})
        self.assertEqual(connect_timeout(), DEFAULT_CONNECT_TIMEOUT)

    def test_non_positive_falls_back(self):
        self._mk(user={"mcp": {"connect_timeout": -3}})
        self.assertEqual(connect_timeout(), DEFAULT_CONNECT_TIMEOUT)


class TestLoadServers(_Base):
    def test_global_disabled_returns_empty(self):
        self._mk(user={"mcp": {"enabled": False, "servers": {"s": {"command": "x"}}}})
        self.assertEqual(load_servers(), {})

    def test_servers_not_dict_returns_empty(self):
        self._mk(user={"mcp": {"enabled": True, "servers": [1, 2]}})
        self.assertEqual(load_servers(), {})

    def test_invalid_server_skipped_keeps_valid(self):
        self._mk(user={"mcp": {"enabled": True, "servers": {
            "good": {"command": "npx", "args": ["-y", "srv"]},
            "bad-no-command": {},
            "bad-args": {"command": "c", "args": "not-a-list"},
        }}})
        servers = load_servers()
        self.assertEqual(set(servers), {"good"})
        self.assertIsInstance(servers["good"], McpServerConfig)

    def test_parses_valid_server_fields(self):
        self._mk(user={"mcp": {"enabled": True, "servers": {
            "fs": {"command": " npx ", "args": ["-y"], "env": {}, "cwd": "~/work", "enabled": True},
        }}})
        cfg = load_servers()["fs"]
        self.assertEqual(cfg.name, "fs")
        self.assertEqual(cfg.command, "npx")  # 前后空白被 strip
        self.assertTrue(str(cfg.cwd).endswith("work"))


class TestGetServer(_Base):
    def test_get_server_present(self):
        self._mk(user={"mcp": {"enabled": True, "servers": {"fs": {"command": "npx"}}}})
        cfg = get_server("fs")
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg.name, "fs")

    def test_get_server_absent_returns_none(self):
        self._mk(user={"mcp": {"enabled": True, "servers": {"fs": {"command": "npx"}}}})
        self.assertIsNone(get_server("other"))

    def test_get_server_when_global_disabled_returns_none(self):
        self._mk(user={"mcp": {"enabled": False, "servers": {"fs": {"command": "npx"}}}})
        self.assertIsNone(get_server("fs"))


if __name__ == "__main__":
    unittest.main()