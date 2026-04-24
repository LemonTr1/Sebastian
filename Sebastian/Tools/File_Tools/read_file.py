from agents import function_tool
import typer
import os

@function_tool
def read_file(path: str, filename: str)->str:
    """
    以字符串形式返回目标文件内的文本内容
    Args:
        path: 文件所在路径
        filename: 文件名
    Returns:
        content：字符串形式的文件的文本内容
    """
    typer.echo("[执行中]正在读取文件内容")
    file_path = os.path.join(path, filename)
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()   # 整个文件 → 一个字符串
    return content