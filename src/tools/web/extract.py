import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from ddgs import DDGS
from src.security.url_safety import is_public_url


def _ddgs_extract(url: str) -> dict:
    with DDGS() as ddgs:
        content = ddgs.extract(url, fmt="text_markdown")
        extracted = content.get("content")
        if extracted is None:
            extracted = "网页无有效文本内容"
        return {"success": True, "content": str(extracted)}


def web_extract(url: str, timeout: int = 20) -> str:
    if not is_public_url(url):
        return json.dumps(
            {
                "success": False,
                "content": "拒绝：非法/内网URL"
            },
            ensure_ascii=False
        )
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_ddgs_extract, url)
            result = future.result(timeout=timeout)
        return json.dumps(
            result,
            ensure_ascii=False
        )
    except FutureTimeoutError:
        return json.dumps(
            {
                "success": False,
                "content": "提取超时"
            },
            ensure_ascii=False
        )
    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "content": str(e)
            },
            ensure_ascii=False
        )


WEB_EXTRACT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "web_extract",
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
