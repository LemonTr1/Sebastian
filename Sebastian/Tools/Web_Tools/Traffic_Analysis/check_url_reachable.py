import aiohttp
import asyncio
import ssl
import typer
from typing import Any, Dict
from agents import function_tool

@function_tool
async def acheck_url_reachable(url: str, timeout: int = 5) -> Dict[str, Any]:
    """
    测试当前网络到url的连通性
    Args:
        url: 目标网址（字符串类型）
        timeout: 超时时间（默认为5秒）
    Returns:
        结构化字典，包含url, reachable, status_code, error, elapsed_sec字段
    """
    typer.echo(typer.style(f"[执行中]正在测试{url}的网络连通性...",fg=typer.colors.WHITE))
    result = {
        "url": url,
        "reachable": False,
        "status_code": None,
        "error": None,
        "elapsed_sec": None,
    }
    # 创建忽略SSL验证的上下文（按需使用）
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    timeout_obj = aiohttp.ClientTimeout(total=timeout)
    try:
        start = asyncio.get_event_loop().time()
        async with aiohttp.ClientSession(
            timeout=timeout_obj,
            headers={"User-Agent": "ConnectivityAgent/1.0"}
        ) as session:
            async with session.get(url, ssl=ssl_context, allow_redirects=True) as resp:
                elapsed = asyncio.get_event_loop().time() - start
                result["reachable"] = resp.status < 400
                result["status_code"] = resp.status
                result["elapsed_sec"] = round(elapsed, 3)
    except asyncio.TimeoutError:
        result["error"] = f"Timeout after {timeout}s"
    except aiohttp.ClientConnectionError:
        result["error"] = "Connection failed"
    except aiohttp.ClientError as e:
        result["error"] = str(e)
    return result