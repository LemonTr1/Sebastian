# 该文件测试 ToolsRegistry 的注册、覆盖、重名、按 agent 过滤、hitl 标注拆分及工具元唯一性。
import unittest

from src.tools.tools_registry import ToolsRegistry


class TestToolsRegistry(unittest.TestCase):
    def setUp(self):
        self.reg = ToolsRegistry()

    def _schema(self, name):
        return {"type": "function", "function": {"name": name}}

    def test_register_and_get(self):
        fn = lambda: "ok"
        self.reg.register_tool("foo", fn, self._schema("foo"))
        got = self.reg.get_tool("foo")
        self.assertIsNotNone(got)
        self.assertIs(got[0], fn)
        self.assertEqual(got[1], self._schema("foo"))

    def test_register_twice_keeps_first(self):
        fn1 = lambda: "one"
        fn2 = lambda: "two"
        self.reg.register_tool("foo", fn1, self._schema("foo"))
        self.reg.register_tool("foo", fn2, self._schema("foo_v2"))
        got = self.reg.get_tool("foo")
        self.assertIs(got[0], fn1)
        self.assertEqual(got[1], self._schema("foo"))

    def test_get_missing_tool_returns_none(self):
        self.assertIsNone(self.reg.get_tool("nope"))
        self.assertFalse(self.reg.is_hitl_tool("nope"))

    def test_hitl_flag_stores_tool(self):
        self.reg.register_tool("w", lambda: 1, self._schema("w"), hitl=True)
        self.assertTrue(self.reg.is_hitl_tool("w"))

    def test_non_hitl_tool_not_flagged(self):
        self.reg.register_tool("r", lambda: 1, self._schema("r"))
        self.assertFalse(self.reg.is_hitl_tool("r"))

    def test_get_tools_for_agent_filters_by_name(self):
        self.reg.register_tool("r", lambda: 1, self._schema("r"), for_agent="A")
        self.reg.register_tool("w", lambda: 2, self._schema("w"), hitl=True, for_agent="A")
        self.reg.register_tool("other", lambda: 3, self._schema("x"), for_agent="B")
        tools, hitl = self.reg.get_tools_for_agent("A")
        self.assertEqual({t[0] for t in tools}, {self.reg.get_tool("r")[0], self.reg.get_tool("w")[0]})
        self.assertEqual(hitl, {"w"})

    def test_agent_without_tools_returns_empty(self):
        tools, hitl = self.reg.get_tools_for_agent("none")
        self.assertEqual(tools, [])
        self.assertEqual(hitl, set())

    def test_agent_tool_names_deduplicated(self):
        fn = lambda: 1
        self.reg.register_tool("r", fn, self._schema("r"), for_agent="A")
        self.reg.register_tool("r", fn, self._schema("r"), for_agent="A")
        tools, _ = self.reg.get_tools_for_agent("A")
        self.assertEqual(len(tools), 1)


if __name__ == "__main__":
    unittest.main()