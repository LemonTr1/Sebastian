import os
import typer
from agents import function_tool
import json

#判断是否存在目标文件/目录
@function_tool
async def which(path: str)->str:
    """
    判断目标文件/目录的路径是否存在
    Args:
        path: str类型，表示目标文件/目录的绝对路径
    Returns:
        json格式字符串
        {
            "exist": True表示存在，False表示不存在
            "path": 表示目标文件/目录的绝对路径
        }
    """
    path = os.path.abspath(path)
    typer.echo(typer.style(f"[执行中]正在执行：test {path}", fg=typer.colors.WHITE))
    if os.path.exists(path):
        return json.dumps({
            "exist": True,
            "path": path
        }, ensure_ascii=False, indent=2)
    return json.dumps({
        "exist": False,
        "path": None
    }, ensure_ascii=False, indent=2)