from kreuzberg import extract_file
import typer
from agents import function_tool
import os
from pathlib import Path

HOME = Path.home()

@function_tool
async def extract(file_path: str) -> dict:
    """
    提取PDF，DOCX类型文件的内容
    Args:
        file_path：文件的路径（必须为绝对路径）
    Returns:
        结构化字典 {
            "success": 提取成功为True, 失败为False
            "summary": 操作概要
        }
    """
    file_path = os.path.abspath(file_path)
    if not Path(file_path).is_relative_to(HOME):
        return {
            "success": False,
            "summary": f"操作必须在{str(HOME)}目录下"
        }
    typer.echo(typer.style(f"[执行中]正在提取{file_path}文件内容",fg=typer.colors.WHITE))
    try:
        result = await extract_file(file_path)
        return {
            "success": True,
            "summary": result.content
        }
    except FileNotFoundError as e:
        typer.echo(typer.style(f"[ERROR]文件不存在：{e}",fg=typer.colors.RED))
        return {
            "success": False,
            "summary": f"文件路径不存在：{e}"
        }
    except PermissionError as e:
        typer.echo(typer.style(f"[ERROR]读取{file_path}文件的权限不足：{e}",fg=typer.colors.RED))
        return {
            "success": False,
            "summary": f"权限不足，无法读取：{e}"
        }
    except Exception as e:
        typer.echo(typer.style(f"[ERROR]出现错误：{e}", fg=typer.colors.RED))
        return {
            "success": False,
            "summary": f"出现错误：{e}"
        }
