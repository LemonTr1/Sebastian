from ddgs import DDGS
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import json


def _ddgs_search(query: str, max_results: int):
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=max_results))


def web_search(query: str, max_results: int = 10, timeout: int = 20) -> str:
    result = {"success": False, "result_list": [], "error_message": ""}
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_ddgs_search, query, max_results)
            results = future.result(timeout=timeout)
        result["success"] = True
        result["result_list"] = results
        return json.dumps(
            result,
            ensure_ascii=False
        )
    except FutureTimeoutError:
        result["error_message"] = f"搜索超时({timeout}s)"
        return json.dumps(
            result,
            ensure_ascii=False
        )
    except Exception as e:
        result["error_message"] = str(e)
        return json.dumps(
            result,
            ensure_ascii=False
        )


WEB_SEARCH_SCHEMA = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "使用DuckDuckGo进行网络搜索，返回相关结果列表",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "max_results": {"type": "integer", "description": "最大返回结果数，默认10"},
                "timeout": {"type": "integer", "description": "超时时间(秒)，默认20"},
            },
            "required": ["query"],
        },
    },
}
