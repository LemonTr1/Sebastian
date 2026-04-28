from kreuzberg import extract_file
import typer
from agents import function_tool

@function_tool
async def extract(file_path: str) -> str:
    """
    提取PDF，DOCX类型文件的内容
    Args:
        file_path：文件的路径
    Returns:
        提取成功返回：文件内容字符串
        提取失败返回：报错信息字符串：'文件路径不存在：{e}'/'权限不足，无法读取：{e}'/'出现错误：{e}'
    """
    typer.echo(typer.style(f"[执行中]正在提取{file_path}文件内容",fg=typer.colors.WHITE))
    try:
        result = await extract_file(file_path)
        return result.content
    except FileNotFoundError as e:
        typer.echo(typer.style(f"[ERROR]文件不存在：{e}",fg=typer.colors.RED))
        return f"文件路径不存在：{e}"
    except PermissionError as e:
        typer.echo(typer.style(f"[ERROR]读取{file_path}文件的权限不足：{e}",fg=typer.colors.RED))
        return f"权限不足，无法读取：{e}"
    except Exception as e:
        typer.echo(typer.style(f"[ERROR]出现错误：{e}", fg=typer.colors.RED))
        return f"出现错误：{e}"
