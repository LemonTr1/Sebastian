import os
import typer
from agents import function_tool
from pathlib import Path
import json
from src.Interfaces.Exception.SecurityException import SecurityException
from src.Interfaces.Resolver.SafePathResolver import resolve_safe_path

HOME = Path.home()

@function_tool
def mkdir(path: str, folder: str)->str:
    """
    在指定路径下创建一个新文件夹
    Args:
        path: str类型，表示目标路径，必须为绝对路径
        folder: str类型，表示空文件夹名称
    Returns:
        json格式的字符串：{
            "success"：操作成功返回True,失败返回False,
            "summary": 操作摘要
        }
    """
    try:
        path = resolve_safe_path(path)
    except SecurityException as e:
        return json.dumps({
            "success": False,
            "summary": str(e)
        }, ensure_ascii=False, indent=2)
    dict_path = os.path.join(path, folder)
    if os.path.isdir(dict_path):
        return json.dumps({
            "success": False,
            "summary": f"文件夹已存在：{dict_path}，不需要创建了",
        }, ensure_ascii=False, indent=2)

    try:
        os.makedirs(dict_path, exist_ok=True)
        typer.echo(typer.style(f"[执行中]正在创建目录：{dict_path}", fg=typer.colors.WHITE))
        return json.dumps({
            "success": True,
            "summary": f"创建目录成功：{dict_path}",
        }, ensure_ascii=False, indent=2)
    except OSError as e:
        return json.dumps({
            "success": False,
            "summary": f"系统问题导致创建目录{dict_path}失败：{e}",
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "summary": f"未知错误：{e}"
        }, ensure_ascii=False, indent=2)
