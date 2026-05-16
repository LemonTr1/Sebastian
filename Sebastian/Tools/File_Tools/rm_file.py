import shutil
import typer
from agents import function_tool
import os
import json
from Interface.Exception.SecurityException import SecurityException
from Interface.SafePath import resolve_safe_path

@function_tool
def rm(path: str, filename: str)->str:
    """
    用于删除某一路径下的文件或文件夹
    Args:
        path: str类型，表示父目录路径（必须为绝对路径）
        filename: str类型，表示要删除的文件或目录名称
    Returns:
        json形式的字符串 {
            "success": 操作成功为True,失败为False
            "summary": 表示操作概要
        }
    """
    path = os.path.abspath(path)
    file_path = os.path.join(path, filename)
    try:
        file_path = resolve_safe_path(file_path)
    except SecurityException as e:
        return json.dumps({
            "success": False,
            "summary": str(e)
        }, ensure_ascii=False, indent=2)

    confirmed = typer.confirm(typer.style(f"[Warn]确定要删除文件系统对象：{file_path}吗？", fg=typer.colors.YELLOW))
    if not confirmed:
        typer.echo("已终止本次操作")
        return json.dumps({
            "success": False,
            "summary": f"用户确认终止了本次操作"
        }, ensure_ascii=False, indent=2)

    if os.path.isdir(file_path):
        double_confirmed = typer.confirm(typer.style(f"[Warn] '{file_path}' 是目录，删除将清空所有内容，继续吗？", fg=typer.colors.YELLOW))
        if not double_confirmed:
            typer.echo("已终止本次操作")
            return json.dumps({
                "success": False,
                "summary": f"用户终止了本次操作"
            }, ensure_ascii=False, indent=2)

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
        return json.dumps({
            "success": False,
            "summary": f"权限不足，禁止删除：{e}"
        }, ensure_ascii=False, indent=2)
    except OSError as e:
        return json.dumps({
            "success": False,
            "summary": f"删除操作失败：{e}"
        }, ensure_ascii=False, indent=2)
    return json.dumps({
        "success": True,
        "summary": f"删除成功"
    }, ensure_ascii=False, indent=2)
