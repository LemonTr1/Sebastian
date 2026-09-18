# 测 TokenCaculator 的累计/清空逻辑与进程级单例
import unittest

from src.utils.tokens_caculator import (
    TokenCaculator,
    TOTAL_SESSION_TOKENS,
    get_total_session_tokens,
)


class TestTokenCaculator(unittest.TestCase):
    def test_accumulate_sum(self):
        c = TokenCaculator()
        c.add_token(100)
        c.add_token(50)
        c.add_token(25)
        self.assertEqual(c.accumulate_token(), 175)

    def test_empty_accumulates_zero(self):
        self.assertEqual(TokenCaculator().accumulate_token(), 0)

    def test_clear_resets(self):
        c = TokenCaculator()
        c.add_token(10)
        c.clear()
        self.assertEqual(c.accumulate_token(), 0)
        self.assertEqual(c.tokens_list, [])

    def test_accumulate_empty_call_list_unchanged(self):
        c = TokenCaculator()
        c.add_token(7)
        self.assertEqual(c.accumulate_token(), 7)
        self.assertEqual(c.accumulate_token(), 7)  # 不消耗状态

    def test_add_multiple_and_single_token(self):
        c = TokenCaculator()
        c.add_token(5)
        c.add_token(0)
        c.add_token(-3)
        self.assertEqual(c.accumulate_token(), 2)

    def test_singleton_shared_state(self):
        # get_total_session_tokens 返回同一单例对象
        container = get_total_session_tokens()
        self.assertIs(container, TOTAL_SESSION_TOKENS)
        container.add_token(42)
        self.assertEqual(TOTAL_SESSION_TOKENS.accumulate_token(), 42)
        TOTAL_SESSION_TOKENS.clear()


if __name__ == "__main__":
    unittest.main()