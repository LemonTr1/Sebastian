from agents import function_tool
import typer
import os
from pathlib import Path

HOME = Path.home()

@function_tool
def read_file(path: str, filename: str):
    """
    读取并以字符串形式返回目标文件内的文本内容
    Args:
        path: 父目录路径字符串（必须为绝对路径）
        filename: 文件名（包含扩展名）
    Returns:
        结构化字典 {
            "success": 是否成功读取到文本内容，成功为True,失败为False,
            "summary": 操作摘要
            "content": 目标文件的文本内容
        }
    """
    path = os.path.abspath(path)
    if not Path(path).is_relative_to(HOME):
        return {
            "success": False,
            "summary": f"路径必须必须在用户主目录{str(HOME)}下",
            "content": None
        }
    file_path = os.path.join(path, filename)

    if not os.path.isfile(file_path):
        typer.echo(typer.style(f"[ERROR]不存在目标文件{file_path}",fg=typer.colors.RED))
        return {
            "success": False,
            "summary": f"不存在目标文件:{file_path}",
            "content": None
        }

    typer.echo(typer.style(f"[执行中]正在读取 {file_path} 的文件内容", fg=typer.colors.WHITE))
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()   # 整个文件 → 一个字符串
        return {
            "success": True,
            "summary": f"成功读取到目标文件{file_path}的内容",
            "content": content
        }
    except Exception as e:
        return {
            "success": False,
            "summary": f"发生错误：{str(e)}",
            "content": None
        }