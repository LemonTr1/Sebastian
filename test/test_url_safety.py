import socket
import unittest
from unittest.mock import patch

from src.security.url_safety import is_public_url


class TestUrlSafety(unittest.TestCase):
    def test_localhost_hostname_rejected(self):
        self.assertFalse(is_public_url("http://localhost/foo"))
        self.assertFalse(is_public_url("https://localhost.localdomain/"))

    def test_loopback_ip_rejected(self):
        self.assertFalse(is_public_url("http://127.0.0.1/"))
        self.assertFalse(is_public_url("http://[::1]/"))

    def test_private_ip_rejected(self):
        self.assertFalse(is_public_url("http://10.0.0.1/"))
        self.assertFalse(is_public_url("http://192.168.1.1/"))
        self.assertFalse(is_public_url("http://172.16.5.5/"))
        self.assertFalse(is_public_url("http://169.254.1.1/"))

    def test_mapped_ipv6_loopback_rejected(self):
        self.assertFalse(is_public_url("http://[::ffff:127.0.0.1]/"))

    def test_public_ip_allowed(self):
        self.assertTrue(is_public_url("https://8.8.8.8/"))
        self.assertTrue(is_public_url("http://1.1.1.1/dns-query"))

    def test_non_http_scheme_rejected(self):
        self.assertFalse(is_public_url("file:///etc/passwd"))
        self.assertFalse(is_public_url("ftp://example.com"))
        self.assertFalse(is_public_url("not-a-url"))

    @patch("src.security.url_safety.socket.getaddrinfo")
    def test_hostname_resolving_to_private_rejected(self, mock_gai):
        mock_gai.return_value = [(0, 0, 0, "", ("10.1.2.3", 0))]
        self.assertFalse(is_public_url("http://evil.example/"))

    @patch("src.security.url_safety.socket.getaddrinfo")
    def test_hostname_resolving_to_public_allowed(self, mock_gai):
        mock_gai.return_value = [(0, 0, 0, "", ("1.1.1.1", 0))]
        self.assertTrue(is_public_url("http://example.com/"))

    @patch("src.security.url_safety.socket.getaddrinfo")
    def test_dns_failure_is_closed(self, mock_gai):
        mock_gai.side_effect = socket.gaierror("name or service not known")
        self.assertFalse(is_public_url("http://does-not-resolve.invalid/"))


if __name__ == "__main__":
    unittest.main()
