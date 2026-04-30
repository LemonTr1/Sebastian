from ddgs import DDGS
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import json
import typer
from agents import function_tool

def ddgs_search(word: str, max_results: int):
    with DDGS() as ddgs:
        return list(ddgs.text(word, max_results=max_results))

@function_tool
def text_search(word: str, max_results: int = 5, timeout: int = 20) -> str:
    """
    DuckDuckGo文本搜索工具
    Args:
        word: 查询内容
        max_results: 最大返回内容数（默认为5条结果）
        timeout: 最大超时限制时间（默认为20s）
    Returns:
        json字符串：{ 
            "success": bool,
            "result_list": list #搜索结果列表
            "error_message" str #错误信息，如果成功则为空
        }
    """
    result = {
        "success": False,
        "result_list": [],
        "error_message": ""
    }

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(ddgs_search, word, max_results)
            results = future.result(timeout=timeout)

        result["success"] = True
        result["result_list"] = results
        return json.dumps(result, ensure_ascii=False)

    except TimeoutError as e:
        result["error_message"] = f"搜索超时:{e}"
        typer.echo(typer.style(f"[ERROR]搜索超时:{e}", fg=typer.colors.RED))
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        result["error_message"] = f"出现错误：{e}"
        typer.echo(typer.style(f"[ERROR]出现错误：{e}",fg=typer.colors.RED))
        return json.dumps(result, ensure_ascii=False)


