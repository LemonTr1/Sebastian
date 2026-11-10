"""测试 src/utils/path_policy.py：只按 settings.json 的 deny_read / read_only 校验，不限制家目录。"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.utils.path_policy import denied_roots, is_denied, read_only_roots, resolve_path
from src.utils.exceptions import SecurityException


def _policy(deny_read=None, read_only=None) -> dict:
    return {"deny_read": deny_read or [], "read_only": read_only or []}


class TestPathPolicy(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(
            prefix=".sebastian-test-", dir=str(Path(__file__).resolve().parents[1])
        )
        self.dir = Path(self._tmp.name)
        self.ok = self.dir / "ok.txt"
        self.ok.write_text("hello", encoding="utf-8")
        self.secret_dir = self.dir / "secret"
        self.secret_dir.mkdir()
        self.secret = self.secret_dir / "token.txt"
        self.secret.write_text("secret", encoding="utf-8")
        self.config_dir = self.dir / "config"
        self.config_dir.mkdir()
        self.config_file = self.config_dir / "app.conf"
        self.config_file.write_text("cfg", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_outside_home_is_allowed(self):
        with mock.patch("src.utils.path_policy.load_sandbox_config", return_value=_policy()):
            self.assertEqual(resolve_path("/etc/hosts"), str(Path("/etc/hosts").resolve()))

    def test_missing_path_rejected(self):
        with mock.patch("src.utils.path_policy.load_sandbox_config", return_value=_policy()):
            with self.assertRaises(SecurityException):
                resolve_path(str(self.dir / "nope.txt"))

    def test_deny_read_blocks_read_and_write(self):
        with mock.patch(
            "src.utils.path_policy.load_sandbox_config",
            return_value=_policy(deny_read=[str(self.secret_dir)]),
        ):
            with self.assertRaises(SecurityException):
                resolve_path(str(self.secret))
            with self.assertRaises(SecurityException):
                resolve_path(str(self.secret_dir / "new.txt"), must_exist=False, write=True)

    def test_read_only_blocks_write_but_allows_read(self):
        with mock.patch(
            "src.utils.path_policy.load_sandbox_config",
            return_value=_policy(read_only=[str(self.config_dir)]),
        ):
            self.assertEqual(resolve_path(str(self.config_file)), str(self.config_file.resolve()))
            with self.assertRaises(SecurityException):
                resolve_path(str(self.config_file), write=True)
            with self.assertRaises(SecurityException):
                resolve_path(str(self.config_dir / "new.conf"), must_exist=False, write=True)

    def test_tilde_is_expanded(self):
        with mock.patch.dict(os.environ, {"HOME": str(self.dir)}):
            with mock.patch("src.utils.path_policy.load_sandbox_config", return_value=_policy()):
                self.assertEqual(resolve_path("~/ok.txt"), str(self.ok.resolve()))

    def test_denied_roots_expand_tilde(self):
        with mock.patch.dict(os.environ, {"HOME": str(self.dir)}):
            with mock.patch(
                "src.utils.path_policy.load_sandbox_config",
                return_value=_policy(deny_read=["~/secret"], read_only=["~/config"]),
            ):
                self.assertEqual(denied_roots(), [self.secret_dir.resolve()])
                self.assertEqual(read_only_roots(), [self.config_dir.resolve()])

    def test_is_denied_with_precomputed_roots(self):
        roots = [self.secret_dir.resolve()]
        self.assertTrue(is_denied(self.secret, roots))
        self.assertFalse(is_denied(self.ok, roots))

    def test_symlink_target_is_checked(self):
        link = self.dir / "link"
        link.symlink_to(self.secret)
        with mock.patch(
            "src.utils.path_policy.load_sandbox_config",
            return_value=_policy(deny_read=[str(self.secret_dir)]),
        ):
            with self.assertRaises(SecurityException):
                resolve_path(str(link))


if __name__ == "__main__":
    unittest.main()
