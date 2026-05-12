import os
import typer
from agents import function_tool

@function_tool
def create_file(path: str, filename: str)->dict:
    """
    在指定路径下建立新的空文件
    Args:
        path: 父目录路径（若不存在，可交互确认后自动创建）
        filename: 文件名（包含扩展名）
    Returns:
        结构化字典 {
            "success"：操作成功为True，失败为False,
            "summary"：操作概要
            "need_confirmed": 是否需要用户确认，是则为True，否则为False
        }
    """
    path = os.path.abspath(path)
    if os.path.isfile(path):
        typer.echo(typer.style(f"[ERROR]父路径{path}已存在且为文件，无法在其中创建文件",fg=typer.colors.RED))
        return {
            "success": False,
            "summary": f"父路径{path}已存在且为文件，无法在其中创建文件，请求确认是否创建新目录{path}",
            "need_confirmed": True
        }

    #拼接完整路径
    file_path = os.path.join(path, filename)

    if not os.path.exists(path):
        return {
            "success": False,
            "summary": f"路径目录{path}不存在，请求是否同意创建路径目录{path}",
            "need_confirmed": True
        }

    if os.path.exists(file_path):
        confirmed = typer.confirm(typer.style(f"[Warn]文件{file_path}已经存在，覆盖会清空内容，确定吗", fg=typer.colors.YELLOW))
        if not confirmed:
            typer.echo("已终止本次操作")
            return {
                "success": False,
                "summary": f"用户确认终止了本次的操作",
                "need_confirmed": False
            }
    else:
        confirmed = typer.confirm(typer.style(f"[Warn]文件{file_path}不存在，确定要创建吗", fg=typer.colors.YELLOW))
        if not confirmed:
            typer.echo("已终止本次操作")
            return {
                "success": False,
                "summary": f"用户确认终止了本次操作",
                "need_confirmed": False
            }

    try:
        #创建空文件
        with open(file_path, 'w') as f:
            pass
        typer.echo(typer.style(f"[Success]文件{file_path}已创建/覆盖", fg=typer.colors.GREEN))
        return {
            "success": True,
            "summary": f"新文件创建成功！{file_path}已创建/覆盖",
            "need_confirmed": False
        }
    except OSError as e:
        typer.echo(typer.style(f"[Error] 创建文件 {file_path} 失败: {e}", fg=typer.colors.RED))
        return {
            "success": False,
            "summary": f"创建文件{file_path}失败",
            "need_confirmed": False
        }

