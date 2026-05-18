from ddgs import DDGS
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import json
import typer
from agents import function_tool

def ddgs_search(word: str, max_results: int):
    typer.echo(typer.style(f"[执行中]正在进行网页搜索：{word}",fg=typer.colors.WHITE))
    with DDGS() as ddgs:
        return list(ddgs.text(word, max_results=max_results))

@function_tool
def web_search(word: str, max_results: int = 10, timeout: int = 20) -> str:
    """
    网络信息搜索工具
    Args:
        word: str类型，表示查询内容
        max_results: int类型，表示最大返回内容数（默认为10条结果）
        timeout: int类型，表示最大超时限制时间（默认为20s）
    Returns:
        json格式的字符串：{
            "success": 搜索成功为True,失败为False
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


