import json
import shutil
from pathlib import Path
import os
from agents import function_tool
import typer

@function_tool
def mv(
        src: str,
        dst: str
):
    """
    移动文件/目录的位置，或者给文件/目录重命名
    Args:
        src: 源文件/目录（必须使用绝对路径）
        dst: 也必须是绝对路径
             如果dst是文件夹，则会将src移动至dst该目录中
             如果dst是文件，则会将src改为dst（相当于重命名，也有可能改变路径）
    Returns:
        json字符串：{"success": bool, "message": str}
    """
    result = {"success": False, "message": ""}
    #如果源文件/目录不存在
    if not os.path.exists(src):
        result["message"] = f"源文件/目录:{src}不存在，移动/重命名失败"
        typer.echo(typer.style(f"[ERROR]源文件/目录:{src}不存在，移动/重命名失败" ,fg=typer.colors.RED))
        return json.dumps(result, ensure_ascii=False, indent=2)

    #提取出父级目录
    parent_path = Path(dst).parent
    if not os.path.exists(parent_path):
        result["message"] = f"目标文件/目录：{dst}不存在，移动失败"
        typer.echo(typer.style(f"[ERROR]目标文件/目录：{dst}不存在，移动失败", fg=typer.colors.RED))
        return json.dumps(result, ensure_ascii=False, indent=2)

    #移动
    if os.path.isdir(dst):
        typer.echo(typer.style(f"[执行中]正在将移动{src}至{dst}目录下",fg=typer.colors.WHITE))
        try:
            shutil.move(src, dst)
            result["success"] = True
            result["message"] = f"成功将{src}移动至{dst}目录下"
            return json.dumps(result, ensure_ascii=False, indent=2)
        except PermissionError as e:
            typer.echo(typer.style(f"[ERROR]权限不足，移动失败：{e}",fg=typer.colors.RED))
            result["message"] = f"权限不足，移动失败：{e}"
            return json.dumps(result, ensure_ascii=False, indent=2)
        except OSError as e:
            typer.echo(typer.style(f"[ERROR]系统出错：{e}",fg=typer.colors.RED))
            result["message"] = f"系统出错：{e}"
            return json.dumps(result, ensure_ascii=False, indent=2)
    #重命名/覆盖
    else:
        typer.echo(typer.style(f"[执行中]正在将{src}重命名为{dst}，注意：该操作可能会覆写文件", fg=typer.colors.WHITE))
        if os.path.isfile(dst):
            confirmed = typer.confirm(typer.style(f"[Warn]{dst}文件已存在，是否要覆盖？",fg=typer.colors.YELLOW))
            if not confirmed:
                typer.echo("操作已终止")
                result["message"] = f"用户已终止该操作，无需询问第二遍"
                return json.dumps(result, ensure_ascii=False, indent=2)
        try:
            typer.echo(typer.style(f"[执行中]正在将{src}重命名为：{dst}",fg=typer.colors.WHITE))
            shutil.move(src, dst)
            typer.echo(typer.style(f"[执行中]已成功将{src}重命名为：{dst}",fg=typer.colors.WHITE))
            result["success"] = True
            result["message"] = f"成功将{src}重命名为{dst}"
            return json.dumps(result, ensure_ascii=False, indent=2)
        except PermissionError as e:
            typer.echo(typer.style(f"[ERROR]权限不足，操作失败:{e}",fg=typer.colors.RED))
            result["message"] = f"错误权限不足，操作失败:{e}"
            return json.dumps(result, ensure_ascii=False, indent=2)
        except OSError as e:
            typer.echo(typer.style(f"[ERROR]系统发生错误：{e}", fg=typer.colors.RED))
            result["message"] = f"错误：系统发生错误：{e}"
            return json.dumps(result, ensure_ascii=False, indent=2)


