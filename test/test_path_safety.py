import tempfile
import unittest
from pathlib import Path

from src.security.path_safety import resolve_safe_path
from src.utils.exceptions import SecurityException


class TestPathSafety(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix=".sebastian-test-", dir=str(Path.home()))
        self.workdir = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_file_inside_home_allowed(self):
        target = self.workdir / "ok.txt"
        target.write_text("hello", encoding="utf-8")
        resolved = resolve_safe_path(str(target))
        self.assertEqual(Path(resolved).resolve(), target.resolve())

    def test_tilde_path_inside_home_allowed(self):
        target = self.workdir / "tilde.txt"
        target.write_text("hello", encoding="utf-8")
        rel = target.relative_to(Path.home())
        resolved = resolve_safe_path(f"~/{rel}")
        self.assertEqual(Path(resolved).resolve(), target.resolve())

    def test_outside_home_rejected(self):
        with self.assertRaises(SecurityException):
            resolve_safe_path("/etc/passwd")

    def test_symlink_escape_rejected(self):
        outside = Path("/etc/passwd")
        if not outside.exists():
            self.skipTest("/etc/passwd 不存在")
        link = self.workdir / "escape"
        link.symlink_to(outside)
        with self.assertRaises(SecurityException):
            resolve_safe_path(str(link))

    def test_symlink_to_sensitive_dir_rejected(self):
        secret_dir = self.workdir / ".ssh"
        secret_dir.mkdir()
        secret_file = secret_dir / "id_rsa"
        secret_file.write_text("nope", encoding="utf-8")
        link = self.workdir / "not-secret"
        link.symlink_to(secret_file)
        with self.assertRaises(SecurityException):
            resolve_safe_path(str(link))

    def test_write_new_file_checks_parent(self):
        target = self.workdir / "new.txt"
        resolved = resolve_safe_path(str(target), must_exist=False)
        self.assertEqual(Path(resolved).parent.resolve(), self.workdir.resolve())

    def test_write_missing_parent_rejected(self):
        target = self.workdir / "missing-dir" / "new.txt"
        with self.assertRaises(SecurityException):
            resolve_safe_path(str(target), must_exist=False)

    def test_broken_symlink_rejected(self):
        link = self.workdir / "broken"
        link.symlink_to(self.workdir / "does-not-exist")
        with self.assertRaises(SecurityException):
            resolve_safe_path(str(link))


if __name__ == "__main__":
    unittest.main()
