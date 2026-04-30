import typer
from agents import function_tool
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from Interface.check_url import is_public_url
from ddgs import DDGS
import json

def ddgs_extract(url: str)->dict:
    try:
        typer.echo(typer.style(f"[执行中]正在提取{url}页面的内容...", fg=typer.colors.WHITE))
        with DDGS() as ddgs:
            content = ddgs.extract(url, fmt="text_markdown")
            extracted = content.get("content")
            if extracted is None:
                extracted = "网页无有效文本内容"
            typer.echo(typer.style(f"提取成功",fg=typer.colors.WHITE))
            return {"success": True, "content": str(extracted)}
    except Exception as e:
        typer.echo(typer.style(f"[ERROR]出现错误：{e}",fg=typer.colors.RED))
        return {"success": False, "content": f"出现错误：{e}"}

@function_tool
def web_extract(url: str, timeout: int = 20)->str:
    """
    网页内容提取
    Args:
        url: 目标网页的完整url地址
        timeout: 最大超时限制（默认20秒）
    Returns:
        json字符串：{"success": bool, "content": str}
    """
    #检查url的安全性
    if not is_public_url(url):
        typer.echo(typer.style("[Rejected]非法url,已拒绝访问", fg=typer.colors.RED))
        return json.dumps({"success": False, "content": "访问拒绝：非法url"}, ensure_ascii=False)

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(ddgs_extract, url)
            result_dict = future.result(timeout=timeout)
        return json.dumps(result_dict, ensure_ascii=False, indent=2)
    except TimeoutError as e:
        typer.echo(typer.style(f"[ERROR]提取超时：{e}", fg=typer.colors.RED))
        return json.dumps({"success": False, "content": "错误:提取超时"}, ensure_ascii=False)
    except Exception as e:
        typer.echo(typer.style(f"[ERROR]出现错误：{e}",fg=typer.colors.RED))
        return json.dumps({"success": False, "content": f"错误：{e}"}, ensure_ascii=False)
