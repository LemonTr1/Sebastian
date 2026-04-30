import json
import time
from agents import function_tool
from ddgs import DDGS
import typer

@function_tool
def news_search(word: str, max_results: int = 5):
    """
    搜索新闻，优先用专业新闻源，无结果时自动降级到近期网页搜索。
    Args:
        word: 搜索关键词
        max_results: 最大结果数
    Returns:
        json字符串{"success": True, "result_list": list, "error_message": str}
    """
    result = {"success": False, "result_list": [], "error_message": ""}

    # 第一步：尝试新闻搜索（多后端重试）
    typer.echo(typer.style(f"[执行中]正在进行新闻搜索...", fg=typer.colors.WHITE))
    backends = ["duckduckgo", "bing"]
    news_results = []
    last_error = ""
    for backend in backends:
        try:
            with DDGS() as ddgs:
                data = list(ddgs.news(word, max_results=max_results, backend=backend))
                if data:
                    news_results = data
                    break
        except Exception as e:
            last_error = str(e)
            time.sleep(1)

    if news_results:
        result["success"] = True
        result["result_list"] = news_results
        return json.dumps(result, ensure_ascii=False)

    # 第二步：新闻搜索无结果，降级到通用网页搜索（限时一周）
    typer.echo(typer.style(f"[执行中]新闻搜索失败，正在进行网页搜索...",fg=typer.colors.WHITE))
    try:
        with DDGS() as ddgs:
            fallback = list(ddgs.text(word, max_results=max_results, timelimit="w"))
            if fallback:
                result["success"] = True
                result["result_list"] = fallback
                return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        last_error += f" | Fallback error: {e}"

    # 全部失败
    result["error_message"] = f"新闻搜索及降级均失败: {last_error}"
    return json.dumps(result, ensure_ascii=False)