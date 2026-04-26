from agents import function_tool
import typer
import os

@function_tool
def read_file(path: str, filename: str):
    """
    以字符串形式返回目标文件内的文本内容
    Args:
        path: 父目录路径字符串
        filename: 文件名（包含扩展名）
    Returns:
        content：字符串形式的文件的文本内容
        None: 目标文件不存在
    """
    file_path = os.path.join(path, filename)

    if not os.path.exists(file_path):
        typer.echo(typer.style(f"[ERROR]目标文件路径不存在",fg=typer.colors.RED))
        return None

    typer.echo(f"[执行中]正在读取 {file_path} 的文件内容")
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()   # 整个文件 → 一个字符串
    return content