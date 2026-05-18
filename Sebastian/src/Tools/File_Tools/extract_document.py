from kreuzberg import extract_file
import typer
from agents import function_tool
import json

from src.Interfaces.Exception import SecurityException
from src.Interfaces.SafePath import resolve_safe_path

@function_tool
async def extract(file_path: str) -> str:
    """
    提取PDF，DOCX类型文件的内容
    Args:
        file_path：str类型，表示文件的路径（必须为绝对路径）
    Returns:
        json格式的字符串 {
            "success": 提取成功为True, 失败为False
            "summary": 操作概要
        }
    """
    try:
        file_path = resolve_safe_path(file_path)
    except SecurityException as e:
        return json.dumps({
            "success": False,
            "summary": str(e)
        }, ensure_ascii=False, indent=2)
    typer.echo(typer.style(f"[执行中]正在提取{file_path}文件内容",fg=typer.colors.WHITE))
    try:
        result = await extract_file(file_path)
        return json.dumps({
            "success": True,
            "summary": result.content
        }, ensure_ascii=False, indent=2)
    except FileNotFoundError as e:
        return json.dumps({
            "success": False,
            "summary": f"文件路径不存在：{e}"
        }, ensure_ascii=False, indent=2)
    except PermissionError as e:
        return json.dumps({
            "success": False,
            "summary": f"权限不足，无法读取：{e}"
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "summary": f"出现错误：{e}"
        }, ensure_ascii=False, indent=2)
