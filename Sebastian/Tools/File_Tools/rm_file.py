import shutil

import typer
from agents import function_tool
import os

@function_tool
def rm(path: str, filename: str)->bool:
    """
    用于删除某一路径下的文件或文件夹
    Args:
        path: 文件系统对象所在路径
        filename: 文件系统对象名称
    Returns:
        True/False: 是否成功删除文件系统对象
    """
    file_path = os.path.join(path, filename)
    if not os.path.exists(file_path):
        typer.echo(typer.style("[Warn]文件或路径不存在",fg=typer.colors.YELLOW))
        return False
    confirmed = typer.confirm(typer.style(f"[Warn]确定要删除文件系统对象：{file_path}吗？", fg=typer.colors.YELLOW))
    if not confirmed:
        typer.echo("已终止本次操作")
        return False

    try:
        if os.path.isfile(file_path):
            #删除文件
            os.remove(file_path)
            print(f"文件已删除: {file_path}")
        elif os.path.isdir(file_path):
            #删除文件夹
            shutil.rmtree(file_path)
            print(f"文件夹已删除: {file_path}")
    except PermissionError:
        print(f"权限不足，禁止删除: {file_path}")
        return False
    except Exception as e:
        print(f"删除操作失败: {e}")
        return False
    return True
