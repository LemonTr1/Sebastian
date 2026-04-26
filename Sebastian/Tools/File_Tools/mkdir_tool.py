import os
import typer
from agents import function_tool

@function_tool
def mkdir(path: str, folder: str)->bool:
    """
    在path路径下创建空文件夹dict
    Args:
        path: 路径字符串
        folder: 空文件夹名称
    Returns:
        True: 目录已经存在或创建成功
        False: 用户取消创建或创建失败
    """
    dict_path = os.path.join(path, folder)
    if os.path.exists(dict_path):
        typer.echo(typer.style(f"[Warn]目录{dict_path}已存在", fg=typer.colors.YELLOW))
        return True

    confirmed = typer.confirm(typer.style(f"[Warn]目录{dict_path}不存在，是否要创建？",fg=typer.colors.YELLOW))
    if not confirmed:
        typer.echo("用户已终止本次操作")
        return False

    try:
        os.makedirs(dict_path, exist_ok=True)
        typer.echo(f"[执行中]正在创建目录：{dict_path}")
        return True
    except OSError as e:
        typer.echo(typer.style(f"[Error]创建目录{dict_path}失败:{e}", fg=typer.colors.RED))
        return False
