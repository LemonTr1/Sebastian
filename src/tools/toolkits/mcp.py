"""MCP 工具桥接：把 settings.json 中启用的 MCP server 暴露的工具注册进 ToolsRegistry。

本模块被 src/tools/__init__.py 自动加载。在模块 import 时（CLI 启动早期）：
- 读取已启用的 MCP server；
- 逐个连接（McpStdioClient.start()→list_tools()），把每个对外工具注册成
  Agent 可调用的工具，命名 `<server>__<tool>`，函数转发给 call_tool()；
- 持有 client 引用，进程退出时经 atexit 统一 stop()，避免泄漏子进程/事件循环线程。

优雅降级：MCP 全局关闭、server 连接或枚举失败、fastmcp 未安装等情况，
一律记日志并跳过，绝不让异常冒泡导致 CLI 启动崩溃。
"""
from __future__ import annotations

import atexit
import json
import threading
from typing import Any

from src.logs.app_log import get_log
from src.mcp import McpStdioClient, load_servers
from src.tools.tools_registry import get_tools_registry

logger = get_log()

FOR_AGENT = "Brain_Agent"

# 已在注册成功的 server 名 → 已启动且保持连接的客户端
_ACTIVE: dict[str, McpStdioClient] = {}
_register_lock = threading.Lock()
_atexit_registered = False


def _make_tool_schema(full_name: str, tool: dict) -> dict:
    """把 MCP 工具的 input_schema 转成 OpenAI function 风格 schema。"""
    parameters = tool.get("input_schema") or {}
    if not isinstance(parameters, dict):
        parameters = {}
    return {
        "type": "function",
        "function": {
            "name": full_name,
            "description": tool.get("description") or "",
            "parameters": parameters,
        },
    }


def _make_call(client: McpStdioClient, full_name: str, tool_name: str) -> Any:
    """生成绑定到指定 client+tool 的可调用对象（Agent 用 func(**args) 调用）。"""
    def _call(**kwargs):
        try:
            result = client.call_tool(tool_name, kwargs)
            payload = {
                "success": not bool(result.get("is_error")),
                "result": result.get("content") or [],
            }
            if result.get("is_error"):
                payload["error"] = "MCP 工具执行失败，详见 result"
            return json.dumps(payload, ensure_ascii=False)
        except Exception as e:  # 夹具兜底：工具报错作为结果返回，不当作 Agent 崩溃
            logger.error(f"[mcp] 调用 {full_name} 出错：{e}")
            return json.dumps(
                {"success": False, "error": f"MCP 工具调用异常：{e}"},
                ensure_ascii=False,
            )

    _call.__qualname__ = f"mcp_call({full_name})"
    _call.__name__ = full_name
    return _call


def register_mcp_tools() -> dict[str, McpStdioClient]:
    """连接全部已启用的 MCP server，并把它们的工具注册进 ToolsRegistry。

    返回实际保持连接的客户端映射（供测试/生命周期使用）。线程安全、幂等。
    """
    global _atexit_registered
    with _register_lock:
        servers = load_servers()  # 全局/单条禁用已在此剔除
        for name, _cfg in servers.items():
            if name in _ACTIVE:
                continue
            client = None
            try:
                client = McpStdioClient.from_settings(name)
                client.start()  # 成功→打印终端+写日志；失败→只写日志并抛 McpStartError
                tools = client.list_tools()
            except Exception as e:
                if client is not None:
                    try:
                        client.stop()
                    except Exception:
                        pass
                logger.error(f"[mcp] 接入 server '{name}' 失败，已跳过：{e}")
                continue

            for tool in tools:
                full = f"{name}__{tool['name']}"
                try:
                    get_tools_registry().register_tool(
                        full,
                        _make_call(client, full, tool["name"]),
                        _make_tool_schema(full, tool),
                        for_agent=FOR_AGENT,
                    )
                except Exception as e:
                    logger.error(f"[mcp] 注册工具 {full} 失败：{e}")
            _ACTIVE[name] = client

        if _ACTIVE and not _atexit_registered:
            atexit.register(_shutdown_mcp_clients)
            _atexit_registered = True
        return dict(_ACTIVE)


def _shutdown_mcp_clients() -> None:
    """进程退出时关闭所有保持连接的 MCP 客户端。"""
    for name, client in list(_ACTIVE.items()):
        try:
            client.stop()
        except Exception as e:
            logger.warning(f"[mcp] 关闭 server '{name}' 出错：{e}")
    _ACTIVE.clear()


# 模块 import 时执行一次注册（被 src/tools/__init__.py 自动加载）
try:
    register_mcp_tools()
except Exception as e:  # 顶级兜底：绝不阻断 CLI 启动
    logger.error(f"[mcp] MCP 工具注册入口异常：{e}")