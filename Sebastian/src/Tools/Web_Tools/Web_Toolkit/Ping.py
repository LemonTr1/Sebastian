import json

import aiohttp
import asyncio
import ssl
import typer
from agents import function_tool

@function_tool
async def acheck_url_reachable(url: str, timeout: int = 5) -> str:
    """
    测试当前网络到url的连通性
    Args:
        url: str类型，目标网址（字符串类型）
        timeout: int类型，超时时间（默认为5秒）
    Returns:
        json格式字符串
        {
            "url": 目标网址
            "reachable":可达为True,不可达为False,
            "status_code": 状态码,
            "error": 错误信息，
            "elapsed_sec": 耗时（单位秒）
        }
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
    return json.dumps(result, ensure_ascii=False, indent=2)