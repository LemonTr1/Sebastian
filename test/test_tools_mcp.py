"""测试 src/tools/toolkits/mcp.py：mock 掉 load_servers/McpStdioClient 后验证无 server、注册命名/function schema、
func 转发 call_tool、is_error 映射及注册失败的降级路径。"""
import json
import os
import tempfile
import unittest
from unittest import mock

# 先隔离真实 ~/.sebastian，避免读写用户配置/日志
_TMP_HOME = tempfile.mkdtemp(prefix="seb-mt-test-")
os.environ["HOME"] = _TMP_HOME

# 导入 src.tools.toolkits.mcp 会触发模块顶部的 register_mcp_tools()，
# 因此在导入前先把 src.mcp 的 load_servers/McpStdioClient mock 掉，避免拉起真实 server。
import src.mcp as _mcp
_auto_servers = mock.patch.object(_mcp, "load_servers", return_value={})
_auto_servers.start()
_auto_client = mock.patch.object(_mcp, "McpStdioClient")
_auto_client.start()

import src.tools.toolkits.mcp as mcp_tools

_auto_servers.stop()
_auto_client.stop()

from src.tools.tools_registry import ToolsRegistry
from src.mcp.config import McpServerConfig

FOR_AGENT = mcp_tools.FOR_AGENT


def _fs_config(name="fs") -> McpServerConfig:
    return McpServerConfig(name=name, command="npx", args=["-y", "srv"], enabled=True)


def _client_for(tools, call_result=None, call_exc=None, start_exc=None):
    client = mock.Mock()
    client.list_tools.return_value = tools
    if call_exc is not None:
        client.call_tool.side_effect = call_exc
    else:
        default_result = {"is_error": False, "content": [{"type": "text", "text": "ok"}]}
        client.call_tool.return_value = call_result if call_result is not None else default_result
    if start_exc is not None:
        client.start.side_effect = start_exc
    return client


class McpBridgeBase(unittest.TestCase):
    def setUp(self):
        # 用全新的 ToolsRegistry 隔离测试间的注册表，避免共享单例污染
        self.registry = ToolsRegistry()
        mcp_tools.get_tools_registry = mock.Mock(return_value=self.registry)
        mcp_tools._ACTIVE.clear()
        mcp_tools._atexit_registered = False

    def _register(self, servers, client_map):
        patcher = mock.patch.object(mcp_tools, "load_servers", return_value=servers)
        patcher.start()
        self.addCleanup(patcher.stop)
        mcp_tools.McpStdioClient.from_settings = mock.Mock(side_effect=lambda n: client_map[n])
        return mcp_tools.register_mcp_tools()

    def _func_for(self, server_name, tool_name):
        entry = self.registry.get_tool(f"{server_name}__{tool_name}")
        self.assertIsNotNone(entry)
        return entry[0]


class TestRegisterNoServers(McpBridgeBase):
    def test_no_servers_registers_nothing(self):
        active = self._register({}, {})
        self.assertEqual(active, {})
        self.assertIsNone(self.registry.get_tool("any__tool"))


class TestRegisterWithServers(McpBridgeBase):
    def test_registers_as_server_double_underscore_tool(self):
        tools = [{"name": "read_file", "description": "读出文件", "input_schema": {"type": "object"}}]
        client = _client_for(tools)
        active = self._register({"fs": _fs_config()}, {"fs": client})

        self.assertEqual(active, {"fs": client})
        entry = self.registry.get_tool("fs__read_file")
        self.assertIsNotNone(entry)
        client.start.assert_called_once_with()
        client.list_tools.assert_called_once_with()

    def test_openai_function_schema_shape(self):
        tools = [{"name": "read_file", "description": "desc", "input_schema": {"type": "object", "properties": {"p": {"type": "string"}}}}]
        client = _client_for(tools)
        self._register({"fs": _fs_config()}, {"fs": client})

        schema = self.registry.get_tool("fs__read_file")[1]
        self.assertEqual(schema["type"], "function")
        fn = schema["function"]
        self.assertEqual(fn["name"], "fs__read_file")
        self.assertEqual(fn["description"], "desc")
        self.assertEqual(fn["parameters"], {"type": "object", "properties": {"p": {"type": "string"}}})

    def test_tool_registered_for_brain_agent(self):
        tools = [{"name": "read_file", "description": "d", "input_schema": {"properties": {}}}]
        client = _client_for(tools)
        self._register({"fs": _fs_config()}, {"fs": client})
        self.assertIn("fs__read_file", self.registry.agent_tools[FOR_AGENT])


class TestCallForward(McpBridgeBase):
    def setUp(self):
        super().setUp()
        self.tool_name = "read_file"
        self.tools = [{"name": self.tool_name, "description": "d", "input_schema": {"properties": {}}}]
        self.client = mock.Mock()
        self.client.list_tools.return_value = self.tools

    def _func(self):
        self._register({"fs": _fs_config()}, {"fs": self.client})
        return self._func_for("fs", self.tool_name)

    def test_forwards_kwargs_to_call_tool_and_returns_success_json(self):
        self.client.call_tool.return_value = {"is_error": False, "content": [{"type": "text", "text": "hi"}]}
        func = self._func()
        out = json.loads(func(path="/etc/hosts"))
        self.client.call_tool.assert_called_once_with(self.tool_name, {"path": "/etc/hosts"})
        self.assertTrue(out["success"])
        self.assertEqual(out["result"], [{"type": "text", "text": "hi"}])

    def test_is_error_returns_success_false_with_error(self):
        self.client.call_tool.return_value = {"is_error": True, "content": [{"type": "text", "text": "boom"}]}
        func = self._func()
        out = json.loads(func(x=1))
        self.assertFalse(out["success"])
        self.assertIn("error", out)
        self.assertEqual(out["result"], [{"type": "text", "text": "boom"}])

    def test_exception_inside_call_returns_failure_json(self):
        self.client.call_tool.side_effect = RuntimeError("network down")
        func = self._func()
        out = json.loads(func(x=1))
        self.assertFalse(out["success"])
        self.assertIn("MCP 工具调用异常", out["error"])


class TestDegrade(McpBridgeBase):
    def test_connection_failure_skips_server(self):
        tools = [{"name": "t1", "description": "d", "input_schema": {"properties": {}}}]
        client = _client_for(tools, start_exc=RuntimeError("start fail"))
        with mock.patch.object(mcp_tools, "logger") as lg:
            active = self._register({"fs": _fs_config()}, {"fs": client})
        lg.error.assert_called()
        self.assertEqual(active, {})
        self.assertIsNone(self.registry.get_tool("fs__t1"))

    def test_tool_registration_failure_is_caught(self):
        tools = [{"name": "t1", "description": "d", "input_schema": {"properties": {}}}]
        client = _client_for(tools)
        with mock.patch.object(self.registry, "register_tool", side_effect=Exception("boom")) as reg:
            active = self._register({"fs": _fs_config()}, {"fs": client})
        reg.assert_called_once()
        # 注册失败被降级捕获，server 仍被标记为保持连接，不崩溃
        self.assertEqual(active, {"fs": client})


class TestShutdown(McpBridgeBase):
    def test_shutdown_stops_and_clears_clients(self):
        client = _client_for([])
        mcp_tools._ACTIVE["fs"] = client
        mcp_tools._atexit_registered = True
        mcp_tools._shutdown_mcp_clients()
        client.stop.assert_called_once_with()
        self.assertEqual(mcp_tools._ACTIVE, {})


class TestSchemaHelper(unittest.TestCase):
    def test_missing_input_schema_becomes_empty(self):
        schema = mcp_tools._make_tool_schema("s__t", {"name": "t", "description": "d"})
        self.assertEqual(schema["function"]["parameters"], {})
        self.assertEqual(schema["function"]["description"], "d")


if __name__ == "__main__":
    unittest.main()