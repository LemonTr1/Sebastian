"""stdio 模式的 MCP 客户端。

对外是同步接口，内部独享一条事件循环线程：
fastmcp 的 Client 是 async 的，且其 transport 默认 keep_alive，
连接会绑定到创建它的那个事件循环，因此不能每次调用都新建 loop。

输出约定（两处硬性要求）：
- server 自身写到 stderr 的日志 → 经管道转发进 get_log()，不回显终端
- 仅当 initialize 握手成功（server 真正跑起来）时，才同时打印终端与写入日志
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any, TextIO

import typer

from src.logs.app_log import get_log
from src.mcp.config import McpServerConfig, connect_timeout, get_server

logger = get_log()

LOG_PREFIX = "mcp"
DEFAULT_OP_TIMEOUT = 60.0


class McpError(RuntimeError):
    """MCP 客户端错误基类。"""


class McpConfigError(McpError):
    """配置缺失或非法。"""


class McpStartError(McpError):
    """server 启动或 initialize 握手失败。"""


class _LogModuleHandler(logging.Handler):
    """把第三方库的日志记录转发进 get_log()，不写终端。"""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            # format() 会带上 exc_info 的纯文本回溯；rich 框线只由 Handler 渲染产生
            message = self.format(record)
            if record.levelno >= logging.ERROR:
                log = logger.error
            elif record.levelno >= logging.WARNING:
                log = logger.warning
            else:
                log = logger.info
            log(f"[{LOG_PREFIX}] {message}")
        except Exception:
            pass


def _redirect_fastmcp_logs() -> None:
    """把 fastmcp 自身的库日志从 stderr 控制台改接到 get_log()。

    fastmcp 导入时会给 "fastmcp" logger 挂 RichHandler(stderr) 并置 propagate=False，
    这些库日志会直接打到终端、污染 CLI 输出。这里摘掉它的控制台 handler，
    换成转发进日志文件的 handler（保持 propagate=False，避免再冒泡到 root）。

    注意：只影响客户端进程内 fastmcp 库自身的日志。server 子进程 stderr 由
    _StderrRouter 原样转发，其中的 rich 框线是 server 自己的输出，不做改造。
    """
    flog = logging.getLogger("fastmcp")
    if any(getattr(h, "_sebastian_mcp", False) for h in flog.handlers):
        return
    for handler in flog.handlers[:]:
        flog.removeHandler(handler)
    handler = _LogModuleHandler()
    handler._sebastian_mcp = True  # type: ignore[attr-defined]
    flog.addHandler(handler)
    flog.propagate = False


class _StderrRouter:
    """把 server 子进程的 stderr 管道逐行转发进 get_log()。

    必须交给 Popen 一个真实 fd（它只认 fileno()），所以用 os.pipe 而不是
    自定义的 write() 对象：写端作为 transport 的 log_file，读端由守护线程
    持续抽干——既避免管道写满把 server 卡死，也保证日志实时落盘。
    """

    def __init__(self, name: str):
        self.name = name
        read_fd, write_fd = os.pipe()
        self._reader = os.fdopen(read_fd, "rb", buffering=0)
        # 文本模式仅为匹配 transport 的 log_file: TextIO 签名；
        # 实际只用到它的 fileno()，缓冲设置不影响子进程直写 fd 的行为
        self._writer = os.fdopen(write_fd, "w", encoding="utf-8", newline="")
        self._closed = False
        self._thread = threading.Thread(
            target=self._pump, name=f"mcp-stderr-{name}", daemon=True
        )

    @property
    def errlog(self) -> TextIO:
        """交给 transport 的 log_file，server 的 stderr 直接写进管道。"""
        return self._writer

    def start(self) -> None:
        self._thread.start()

    def detach_writer(self) -> None:
        """server 已 spawn 后调用：关掉父进程这份写端。

        子进程已持有自己 dup 过的 fd，关掉父进程副本能让读端在子进程退出时
        立刻看到 EOF，而不是一直挂着等父进程。
        """
        if self._closed:
            return
        self._closed = True
        try:
            self._writer.close()
        except OSError:
            pass

    def _pump(self) -> None:
        try:
            for raw in self._reader:
                line = raw.decode("utf-8", errors="replace").rstrip()
                if line:
                    logger.info(f"[{LOG_PREFIX}:{self.name}] {line}")
        except (OSError, ValueError):
            pass
        finally:
            try:
                self._reader.close()
            except OSError:
                pass

    def close(self) -> None:
        self.detach_writer()
        self._thread.join(timeout=2)


class McpStdioClient:
    """同步接口的 stdio MCP 客户端，每个实例独享一条事件循环线程。

    典型用法：
        with McpStdioClient.from_settings("filesystem") as client:
            for tool in client.list_tools():
                print(tool["name"])
            client.call_tool("read_file", {"path": "/tmp/a.txt"})
    """

    def __init__(
        self,
        config: McpServerConfig,
        *,
        connect_timeout: float = 30.0,
        op_timeout: float = DEFAULT_OP_TIMEOUT,
    ):
        self.config = config
        self.connect_timeout = connect_timeout
        self.op_timeout = op_timeout
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._client: Any = None
        self._transport: Any = None
        self._stderr: _StderrRouter | None = None
        self._started = False
        self._lock = threading.RLock()

    @classmethod
    def from_settings(cls, name: str, **kwargs) -> "McpStdioClient":
        """按名字从 settings.json 构造客户端。"""
        config = get_server(name)
        if config is None:
            raise McpConfigError(f"settings.json 中未找到 MCP server `{name}`。")
        kwargs.setdefault("connect_timeout", connect_timeout())
        return cls(config, **kwargs)

    # ---- 生命周期 ----

    def start(self) -> dict:
        """启动 server 并完成 initialize 握手。

        成功时同时打印终端与写入日志；失败只写日志并抛 McpStartError，
        终端保持干净。
        """
        with self._lock:
            if self._started:
                return self._server_info()

            if not self.config.enabled:
                raise McpStartError(f"MCP server `{self.config.name}` 已在配置中禁用。")

            stderr = _StderrRouter(self.config.name)
            self._stderr = stderr
            stderr.start()
            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(
                target=self._run_loop,
                name=f"mcp-loop-{self.config.name}",
                daemon=True,
            )
            self._thread.start()

            try:
                self._submit(
                    self._start_async(stderr), timeout=self.connect_timeout + 5
                )
            except Exception as e:
                logger.error(
                    f"[{LOG_PREFIX}] server '{self.config.name}' 启动失败"
                    f"（{self.config.command} {' '.join(self.config.args)}）：{e}"
                )
                self.stop()
                raise McpStartError(
                    f"MCP server `{self.config.name}` 启动失败：{e}"
                ) from e

            self._started = True
            info = self._server_info()
            summary = (
                f"server '{self.config.name}' 启动成功（{self._identity(info)}）"
            )
            logger.info(f"[{LOG_PREFIX}] {summary}")
            typer.echo(typer.style(f"\n> [{LOG_PREFIX}] {summary} \n", fg=typer.colors.GREEN, bold=True))
            return info

    async def _start_async(self, stderr: "_StderrRouter") -> None:
        from fastmcp import Client
        from fastmcp.client.transports import StdioTransport

        _redirect_fastmcp_logs()

        self._transport = StdioTransport(
            **self.config.transport_kwargs(),
            keep_alive=True,
            log_file=stderr.errlog,
        )
        self._client = Client(self._transport, init_timeout=self.connect_timeout)
        await self._client.__aenter__()
        # 握手完成 ⇒ 子进程已 spawn，可以放掉父进程那份写端
        stderr.detach_writer()

    def stop(self) -> None:
        """关闭会话并终止 server 子进程；可重复调用。"""
        with self._lock:
            if self._loop is not None:
                if self._started and self._client is not None:
                    try:
                        self._submit(self._stop_async(), timeout=10)
                    except Exception as e:
                        logger.warning(
                            f"[{LOG_PREFIX}] server '{self.config.name}' 关闭时出错：{e}"
                        )
                try:
                    self._loop.call_soon_threadsafe(self._loop.stop)
                except RuntimeError:
                    pass
                if self._thread is not None:
                    self._thread.join(timeout=5)

            if self._stderr is not None:
                self._stderr.close()

            self._started = False
            self._client = None
            self._transport = None
            self._stderr = None
            self._loop = None
            self._thread = None

    async def _stop_async(self) -> None:
        try:
            await self._client.__aexit__(None, None, None)
        finally:
            # keep_alive=True 时 __aexit__ 不会断开 transport，子进程要显式收掉
            if self._transport is not None:
                await self._transport.disconnect()

    def __enter__(self) -> "McpStdioClient":
        self.start()
        return self

    def __exit__(self, *exc) -> bool:
        self.stop()
        return False

    # ---- 能力调用 ----

    def list_tools(self) -> list[dict]:
        """列出 server 暴露的工具，返回可 JSON 序列化的 dict 列表。"""
        return self._ensure_submit(self._list_tools_async(), self.op_timeout + 5)

    async def _list_tools_async(self) -> list[dict]:
        async with self._client:
            tools = await self._client.list_tools()
        return [self._tool_to_dict(t) for t in tools]

    def call_tool(
        self,
        name: str,
        arguments: dict | None = None,
        *,
        timeout: float | None = None,
    ) -> dict:
        """调用工具，返回 {tool, is_error, content, structured_content}。

        工具自身的报错体现为 is_error=True，不作为异常抛出。
        """
        request_timeout = timeout if timeout is not None else self.op_timeout
        return self._ensure_submit(
            self._call_tool_async(name, arguments or {}, request_timeout),
            request_timeout + 5,
        )

    async def _call_tool_async(
        self, name: str, arguments: dict, timeout: float
    ) -> dict:
        async with self._client:
            result = await self._client.call_tool(
                name, arguments, timeout=timeout, raise_on_error=False
            )
        return {
            "tool": name,
            "is_error": bool(result.is_error),
            "content": [self._block_to_dict(b) for b in (result.content or [])],
            "structured_content": result.structured_content,
        }

    @property
    def is_connected(self) -> bool:
        return bool(self._started and self._client is not None and self._client.is_connected)

    # ---- 内部工具 ----

    def _server_info(self) -> dict:
        """握手结果。

        modern 协议（server/discover）不返回 server_info，此时 name/version 为 None，
        仅 protocol_version 可用——调用方需容忍。
        """
        result = getattr(self._client, "initialize_result", None)
        server_info = getattr(result, "server_info", None)
        return {
            "server": self.config.name,
            "server_name": getattr(server_info, "name", None),
            "server_version": getattr(server_info, "version", None),
            "protocol_version": getattr(self._client, "protocol_version", None) or "unknown",
            "command": self.config.command,
            "args": list(self.config.args),
        }

    @staticmethod
    def _identity(info: dict) -> str:
        parts = []
        if info["server_name"]:
            name = str(info["server_name"])
            if info["server_version"]:
                name += f" {info['server_version']}"
            parts.append(name)
        parts.append(f"protocol {info['protocol_version']}")
        return "，".join(parts)

    @staticmethod
    def _tool_to_dict(tool: Any) -> dict:
        return {
            "name": getattr(tool, "name", ""),
            "title": getattr(tool, "title", None),
            "description": getattr(tool, "description", None) or "",
            "input_schema": getattr(tool, "input_schema", None) or {},
        }

    @staticmethod
    def _block_to_dict(block: Any) -> dict:
        dump = getattr(block, "model_dump", None)
        if callable(dump):
            try:
                dumped = dump(mode="json")
                if isinstance(dumped, dict):
                    return dumped
            except Exception:
                pass
        return {"type": getattr(block, "type", "unknown"), "text": str(block)}

    def _ensure_submit(self, coro, timeout: float):
        with self._lock:
            if not self._started or self._loop is None:
                coro.close()
                raise McpError(
                    f"MCP server `{self.config.name}` 尚未启动，请先调用 start()。"
                )
            return self._submit(coro, timeout)

    def _submit(self, coro, timeout: float):
        """把协程投递到事件循环线程并同步等待结果。"""
        loop = self._loop
        if loop is None:
            coro.close()
            raise McpError(f"MCP server `{self.config.name}` 的事件循环不可用。")

        future = asyncio.run_coroutine_threadsafe(coro, loop)
        try:
            return future.result(timeout)
        except FutureTimeoutError:
            future.cancel()
            raise McpError(
                f"MCP server `{self.config.name}` 操作超时（{timeout}s）。"
            ) from None

    def _run_loop(self) -> None:
        loop = self._loop
        if loop is None:
            return
        asyncio.set_event_loop(loop)
        try:
            loop.run_forever()
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            loop.close()