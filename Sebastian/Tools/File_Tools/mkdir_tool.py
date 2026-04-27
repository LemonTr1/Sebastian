import os
import typer
from agents import function_tool

@function_tool
def mkdir(path: str, folder: str)->str:
    """
    在指定路径下创建一个新文件夹
    Args:
        path: 路径字符串
        folder: 空文件夹名称
    Returns:
        成功时返回：“创建目录成功：{新文件夹路径}”
        失败时返回：“文件夹已存在”/“用户终止了创建新文件夹的操作”/“创建目录失败”
    """
    dict_path = os.path.join(path, folder)
    if os.path.exists(dict_path):
        typer.echo(typer.style(f"[Warn]目录{dict_path}已存在", fg=typer.colors.YELLOW))
        return f"文件夹已存在：{dict_path}"

    confirmed = typer.confirm(typer.style(f"[Warn]目录{dict_path}不存在，是否要创建？",fg=typer.colors.YELLOW))
    if not confirmed:
        typer.echo("用户已终止本次操作")
        return f"用户终止了创建新文件夹的操作"

    try:
        os.makedirs(dict_path, exist_ok=True)
        typer.echo(typer.style(f"[执行中]正在创建目录：{dict_path}", fg=typer.colors.WHITE))
        return f"创建目录成功：{dict_path}"
    except OSError as e:
        typer.echo(typer.style(f"[Error]创建目录{dict_path}失败:{e}", fg=typer.colors.RED))
        return f"创建目录{dict_path}失败"
