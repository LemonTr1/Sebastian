import os
import typer
from agents import function_tool

@function_tool
def create_file(path: str, filename: str)->str:
    """
    在指定路径下建立新的空文件
    Args:
        path: 父目录路径（若不存在，可交互确认后自动创建）
        filename: 文件名（包含扩展名）
    Returns:
        成功时返回：“新文件创建成功！{file_path}已创建/覆盖”
        失败时返回：“父路径{path}已存在且为文件，无法在其中创建文件”/“用户终止了创建路径的操作”/“创建路径{path}失败”/“用户终止了创建新文件的操作”/“创建文件{file_path}失败”
    """
    if os.path.isfile(path):
        typer.echo(typer.style(f"[ERROR]父路径{path}已存在且为文件，无法在其中创建文件",fg=typer.colors.RED))
        return f"父路径{path}已存在且为文件，无法在其中创建文件"

    #拼接完整路径
    file_path = os.path.join(path, filename)

    if not os.path.exists(path):
        confirmed = typer.confirm(typer.style(f"[Warn]{path}路径不存在，你确定要建立该路径吗", fg=typer.colors.YELLOW))
        if not confirmed:
            typer.echo(f"已终止本次操作")
            return f"用户终止了创建路径的操作"
        try:
            os.makedirs(path, exist_ok=True)
            typer.echo(f"[执行中]文件路径{path}已创建")
        except OSError as e:
            typer.echo(typer.style(f"[Error]创建路径{path}失败:{e}",fg=typer.colors.RED))
            return f"创建路径{path}失败：{e}"

    if os.path.exists(file_path):
        confirmed = typer.confirm(typer.style(f"[Warn]文件{file_path}已经存在，覆盖会清空内容，确定吗", fg=typer.colors.YELLOW))
        if not confirmed:
            typer.echo("已终止本次操作")
            return f"用户终止了创建新文件的操作"

    try:
        #创建空文件
        with open(file_path, 'w') as f:
            pass
        typer.echo(f"[执行中]文件{file_path}已创建/覆盖")
        return f"新文件创建成功！{file_path}已创建/覆盖"
    except OSError as e:
        typer.echo(typer.style(f"[Error] 创建文件 {file_path} 失败: {e}", fg=typer.colors.RED))
        return f"创建文件{file_path}失败"

