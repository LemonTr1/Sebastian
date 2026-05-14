import os
import typer
from agents import function_tool

#判断是否存在目标文件/目录
@function_tool
def which(path: str)->bool:
    """
    判断目标文件/目录的路径是否存在
    Args:
        path: 目标文件/目录的绝对路径
    Returns:
        True: 表示存在目标文件/目录
        False: 表示不存在目标文件/目录
    """
    path = os.path.abspath(path)
    typer.echo(typer.style(f"[执行中]正在执行：which {path}", fg=typer.colors.WHITE))
    if os.path.exists(path):
        return True
    typer.echo(typer.style("[ERROR]不存在目标文件/目录", fg=typer.colors.RED))
    return False