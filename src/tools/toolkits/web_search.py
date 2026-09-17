from ddgs import DDGS
from baidusearch.baidusearch import search
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import json
from src.tools.tools_registry import get_tools_registry
from src.logs.app_log import get_log

logger = get_log()

def _ddgs_search(query: str, max_results: int) -> list:
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=max_results))

def _baidu_search(query: str, max_results: int) -> list:
    results = search(query, num_results=max_results)
    return list(results)

def web_search(query: str, max_results: int = 10, timeout: int = 20) -> str:
    result = {"success": False, "result_list": [], "error_message": ""}
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_ddgs_search, query, max_results)
            results = future.result(timeout=timeout)
        result["success"] = True
        result["result_list"] = results
    except FutureTimeoutError:
        result["error_message"] = f"DDGS搜索超时({timeout}s)"
        logger.error(result["error_message"])
    except Exception as e:
        result["error_message"] = str(e)
        logger.error(result["error_message"])
        
    if result["success"]:
        return json.dumps(
                result,
                ensure_ascii=False
            )
    else:
        logger.warning(f"DDGS搜索失败，降级为百度搜索")
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_baidu_search, query, max_results)
                results = future.result(timeout=timeout)
            result["success"] = True
            result["result_list"] = results
        except FutureTimeoutError:
            result["error_message"] = f"Baidu搜索超时({timeout}s)"
            logger.error(result["error_message"])
        except Exception as e:
            result["error_message"] = str(e)
            logger.error(result["error_message"])
        return json.dumps(
                result,
                ensure_ascii=False
            )


WEB_SEARCH_SCHEMA = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "根据关键词进行网络搜索，返回包含url的相关结果列表",
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

get_tools_registry().register_tool("web_search", web_search, WEB_SEARCH_SCHEMA, for_agent="Brain_Agent")
