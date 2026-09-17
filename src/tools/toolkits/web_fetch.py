import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from ddgs import DDGS
import requests
from bs4 import BeautifulSoup
from src.security.url_safety import is_public_url
from src.tools.tools_registry import get_tools_registry
from src.logs.app_log import get_log

logger = get_log()


def _ddgs_extract(url: str) -> dict:
    with DDGS() as ddgs:
        content = ddgs.extract(url, fmt="text_markdown")
        extracted = content.get("content")
        if extracted is None:
            extracted = "网页无有效文本内容"
        return {"success": True, "content": str(extracted)}


def _requests_extract(url: str) -> dict:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    }
    resp = requests.get(url, headers=headers, timeout=15, verify=False)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or resp.encoding
    soup = BeautifulSoup(resp.text, "lxml")
    for tag in soup(["script", "style", "noscript", "footer", "nav", "header"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    # 压缩多余空行
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    content = "\n".join(lines)
    if not content:
        content = "网页无有效文本内容"
    return {"success": True, "content": content}


def web_fetch(url: str, timeout: int = 20) -> str:
    if not is_public_url(url):
        return json.dumps(
            {
                "success": False,
                "content": "拒绝：非法/内网URL"
            },
            ensure_ascii=False
        )

    result = {"success": False, "content": ""}
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_ddgs_extract, url)
            result = future.result(timeout=timeout)
    except FutureTimeoutError:
        result["content"] = "DDGS提取超时"
        logger.error(f"web_fetch DDGS超时({timeout}s): {url}")
    except Exception as e:
        result["content"] = str(e)
        logger.error(f"web_fetch DDGS失败: {e}")

    if not result["success"]:
        logger.warning(f"DDGS提取失败，降级为requests+BeautifulSoup: {url}")
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_requests_extract, url)
                result = future.result(timeout=timeout + 5)
        except FutureTimeoutError:
            result["content"] = "requests提取超时"
            logger.error(f"web_fetch requests超时({timeout + 5}s): {url}")
        except Exception as e:
            result["content"] = str(e)
            logger.error(f"web_fetch requests失败: {e}")

    return json.dumps(
        result,
        ensure_ascii=False
    )


WEB_FETCH_SCHEMA = {
    "type": "function",
    "function": {
        "name": "web_fetch",
        "description": "提取指定URL的网页正文内容（纯文本/markdown）",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "目标网页完整URL"},
                "timeout": {"type": "integer", "description": "超时(秒)，默认20"},
            },
            "required": ["url"],
        },
    },
}

get_tools_registry().register_tool("web_fetch", web_fetch, WEB_FETCH_SCHEMA, for_agent="Brain_Agent")
