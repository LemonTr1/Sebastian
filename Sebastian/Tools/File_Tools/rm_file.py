import shutil
import typer
from agents import function_tool
import os

@function_tool
def rm(path: str, filename: str)->dict:
    """
    用于删除某一路径下的文件或文件夹
    Args:
        path: 父目录路径（必须为绝对路径）
        filename: 要删除的文件或目录名称
    Returns:
        结构化字典 {
            "success": 操作成功为True,失败为False
            "summary": 操作概要
        }
    """
    path = os.path.abspath(path)
    file_path = os.path.join(path, filename)
    if not os.path.exists(file_path):
        typer.echo(typer.style("[ERROR]文件路径不存在",fg=typer.colors.RED))
        return {
            "success": False,
            "summary": f"目标路径不存在：{file_path}"
        }

    confirmed = typer.confirm(typer.style(f"[Warn]确定要删除文件系统对象：{file_path}吗？", fg=typer.colors.YELLOW))
    if not confirmed:
        typer.echo("已终止本次操作")
        return {
            "success": False,
            "summary": f"用户确认终止了本次操作"
        }

    if os.path.isdir(file_path):
        double_confirmed = typer.confirm(typer.style(f"[Warn] '{file_path}' 是目录，删除将清空所有内容，继续吗？", fg=typer.colors.YELLOW))
        if not double_confirmed:
            typer.echo("已终止本次操作")
            return {
                "success": False,
                "summary": f"用户终止了本次操作"
            }

    try:
        if os.path.islink(file_path):
            os.unlink(file_path)
            typer.echo(typer.style(f"[Success]符号链接已删除：{file_path}", fg=typer.colors.GREEN))
        elif os.path.isfile(file_path):
            #删除文件
            os.remove(file_path)
            typer.echo(typer.style(f"[Success]文件已删除: {file_path}", fg=typer.colors.GREEN))
        elif os.path.isdir(file_path):
            #删除文件夹
            shutil.rmtree(file_path)
            typer.echo(typer.style(f"[Success]文件夹已删除: {file_path}", fg=typer.colors.GREEN))
    except PermissionError as e:
        typer.echo(typer.style(f"[ERROR]权限不足，禁止删除: {file_path}", fg=typer.colors.RED))
        return {
            "success": False,
            "summary": f"权限不足，禁止删除：{e}"
        }
    except OSError as e:
        typer.echo(typer.style(f"[ERROR]删除操作失败: {e}", fg=typer.colors.RED))
        return {
            "success": False,
            "summary": f"删除操作失败：{e}"
        }
    return {
        "success": True,
        "summary": f"删除成功"
    }
