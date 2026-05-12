import os
import typer
from agents import function_tool

@function_tool
def mkdir(path: str, folder: str)->dict:
    """
    在指定路径下创建一个新文件夹
    Args:
        path: 路径字符串
        folder: 空文件夹名称
    Returns:
        结构化字典：{
            "success"：操作成功返回True,失败返回False,
            "summary": 操作摘要
        }
    """
    path = os.path.abspath(path)
    dict_path = os.path.join(path, folder)
    if os.path.isdir(dict_path):
        typer.echo(typer.style(f"[Warn]目录{dict_path}已存在", fg=typer.colors.YELLOW))
        return {
            "success": False,
            "summary": f"文件夹已存在：{dict_path}，不需要创建了",
        }

    confirmed = typer.confirm(typer.style(f"[Warn]目录{dict_path}不存在，是否要创建？",fg=typer.colors.YELLOW))
    if not confirmed:
        typer.echo("用户已终止本次操作")
        return {
            "success": False,
            "summary": "用户确认终止了创建新文件夹的操作",
        }

    try:
        os.makedirs(dict_path, exist_ok=True)
        typer.echo(typer.style(f"[执行中]正在创建目录：{dict_path}", fg=typer.colors.WHITE))
        return {
            "success": True,
            "summary": f"创建目录成功：{dict_path}",
        }
    except OSError as e:
        typer.echo(typer.style(f"[Error]创建目录{dict_path}失败:{e}", fg=typer.colors.RED))
        return {
            "success": False,
            "summary": f"创建目录{dict_path}失败",
        }
