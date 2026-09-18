"""MCP 客户端接口（当前仅实现 stdio 传输）。

配置位于 settings.json 的 `mcp` 段，读取逻辑见 src/mcp/config.py。

    from src.mcp import McpStdioClient

    with McpStdioClient.from_settings("filesystem") as client:
        print(client.list_tools())
"""
from src.mcp.config import (
    McpServerConfig,
    connect_timeout,
    get_server,
    load_mcp_settings,
    load_servers,
)
from src.mcp.stdio_client import (
    McpConfigError,
    McpError,
    McpStartError,
    McpStdioClient,
)

__all__ = [
    "McpConfigError",
    "McpError",
    "McpServerConfig",
    "McpStartError",
    "McpStdioClient",
    "connect_timeout",
    "get_server",
    "load_mcp_settings",
    "load_servers",
]