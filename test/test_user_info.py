# 测 get_username 的用户名来源优先级：USER > LOGNAME > getlogin 兜底
import os
import unittest
from unittest.mock import patch

from src.utils.user_info import get_username


class TestGetUsername(unittest.TestCase):
    def test_user_used_when_set(self):
        with patch.dict(os.environ, {"USER": "alice", "LOGNAME": "logalice"}):
            self.assertEqual(get_username(), "alice")

    def test_logname_when_user_missing(self):
        with patch.dict(os.environ, {"USER": "", "LOGNAME": "bob"}):
            self.assertEqual(get_username(), "bob")

    def test_falls_back_to_getlogin(self):
        # 两个环境变量都未设置时回退到 os.getlogin()（mock 掉避免依赖终端）
        with patch.dict(os.environ, {}, clear=True):
            with patch("src.utils.user_info.os.getlogin", return_value="carol"):
                self.assertEqual(get_username(), "carol")

    def test_returns_string(self):
        with patch.dict(os.environ, {"USER": "dave"}, clear=True):
            self.assertIsInstance(get_username(), str)


if __name__ == "__main__":
    unittest.main()