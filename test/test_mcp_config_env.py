"""MCP 配置 env 中 `${VAR}` 引用的展开行为。"""
import os
import unittest
from unittest import mock

from src.mcp.config import _expand_env_value, _parse_server


class TestExpandEnvValue(unittest.TestCase):
    def test_expands_defined_variable(self):
        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_fake_value"}):
            self.assertEqual(
                _expand_env_value("srv", "TOKEN", "${GITHUB_TOKEN}"), "ghp_fake_value"
            )

    def test_expands_inline_within_larger_string(self):
        with mock.patch.dict(os.environ, {"HOST": "example.com"}):
            got = _expand_env_value("srv", "URL", "https://${HOST}/api")
            self.assertEqual(got, "https://example.com/api")

    def test_missing_variable_kept_verbatim(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                _expand_env_value("srv", "TOKEN", "${NOT_SET_ANYWHERE}"),
                "${NOT_SET_ANYWHERE}",
            )

    def test_non_reference_syntax_untouched(self):
        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_fake_value"}):
            # $VAR、${1BAD} 都不属于受支持的 ${VAR} 语法
            self.assertEqual(_expand_env_value("srv", "K", "$GITHUB_TOKEN"), "$GITHUB_TOKEN")
            self.assertEqual(_expand_env_value("srv", "K", "${1BAD}"), "${1BAD}")

    def test_plain_value_untouched(self):
        self.assertEqual(_expand_env_value("srv", "K", "literal-token"), "literal-token")


class TestParseServerEnv(unittest.TestCase):
    def test_parse_server_expands_env(self):
        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_fake_value"}):
            cfg = _parse_server(
                "demo",
                {
                    "command": "npx",
                    "args": ["-y", "some-server"],
                    "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"},
                },
            )
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg.env, {"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_fake_value"})

    def test_parse_server_keeps_literal_when_unset(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = _parse_server("demo", {"command": "npx", "env": {"TOKEN": "${GITHUB_TOKEN}"}})
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg.env, {"TOKEN": "${GITHUB_TOKEN}"})

    def test_expansion_does_not_affect_other_fields(self):
        with mock.patch.dict(os.environ, {"DIR": "/tmp/whatever"}):
            cfg = _parse_server(
                "demo", {"command": "npx", "args": ["${DIR}"], "cwd": "/tmp"}
            )
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg.args, ["${DIR}"])


if __name__ == "__main__":
    unittest.main()
