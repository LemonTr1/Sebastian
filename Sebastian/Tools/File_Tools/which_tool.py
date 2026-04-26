import os
import typer
from agents import function_tool

#判断是否存在目标文件/目录
@function_tool
def which(path: str, filename: str)->bool:
    """
    判断用户给出的路径和文件是否存在
    Args:
        path: 父目录路径字符串
        filename: 目标文件/目录名
    Returns:
        True: 表示存在目标文件/目录
        False: 表示不存在目标文件/目录
    """
    file_path = os.path.join(path, filename)
    typer.echo(f"[执行中]正在执行：which {file_path}")
    if os.path.exists(file_path):
        return True
    typer.echo(typer.style("[ERROR]不存在目标文件/目录", fg=typer.colors.RED))
    return False