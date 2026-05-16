import shutil
import json
import typer
import os
from agents import function_tool
from pathlib import Path
from Interface.SafePath import resolve_safe_path
from Interface.Exception.SecurityException import SecurityException

@function_tool
def cp_file(src: str, dst: str)->str:
    """
    复制文件到目标路径
    Args:
        src: str类型，源文件名称（必须存在且为绝对路径）
        dst: str类型，目标路径（必须存在且为绝对路径）
    Returns:
        json字符串：{
            "success": 操作成功为True,失败为False,
            "message": 操作概要
        }
    """
    try:
        src = resolve_safe_path(src)
    except SecurityException as e:
        return json.dumps({
            "success": False,
            "message": str(e)
        }, ensure_ascii=False, indent=2)

    try:
        dst = resolve_safe_path(dst)
    except SecurityException as e:
        return json.dumps({
            "success": False,
            "message": str(e)
        }, ensure_ascii=False, indent=2)

    result = {"success": False, "message": ""}

    #源文件是否是文件或是否存在
    if not os.path.isfile(src):
        typer.echo(typer.style(f"[ERROR]源文件：{src}不是文件或不存在",fg=typer.colors.RED))
        result["message"] = f"源文件：{src}不是文件或不存在"
        return json.dumps(result, ensure_ascii=False, indent=2)

    #如果dst不存在或不是目录，直接拒绝
    if not os.path.isdir(dst):
        typer.echo(typer.style(f"[ERROR]目标路径不存在或不为目录：{dst}",fg=typer.colors.RED))
        result["message"] = f"目标路径不存在或不为目录：{dst}"
        return json.dumps(result, ensure_ascii=False, indent=2)

    try:
        typer.echo(typer.style(f"[执行中]正在将源文件：{src} 复制到 {dst} 目录下...",fg=typer.colors.WHITE))
        shutil.copy2(src, dst)
        typer.echo(typer.style(f"[Success]复制成功！",fg=typer.colors.GREEN))
        result["success"] = True
        result["message"] = "复制成功"
        return json.dumps(result, ensure_ascii=False, indent=2)
    except shutil.SameFileError as e:
        typer.echo(typer.style(f"[ERROR]源和目标指向同一个文件 ({src})，未执行复制：{e}", fg=typer.colors.RED))
        result["message"] = f"错误: 源和目标指向同一个文件 ({src})，未执行复制：{e}"
        return json.dumps(result, ensure_ascii=False, indent=2)
    except PermissionError as e:
        typer.echo(typer.style(f"[ERROR]权限不足，复制失败：{e}", fg=typer.colors.RED))
        result["message"] = f"权限不足，复制失败：{e}"
        return json.dumps(result, ensure_ascii=False, indent=2)
    except OSError as e:
        typer.echo(typer.style(f"[ERROR]未知错误：{e}", fg=typer.colors.RED))
        result["message"] = f"未知错误：{e}"
        return json.dumps(result, ensure_ascii=False, indent=2)

@function_tool
def cp_dict(src: str, dst: str)->str:
    """
    递归复制整个目录到目标路径
    Args:
        src: str类型，源目录名称（必须存在且是绝对路径）
        dst: str类型目标路径（必须存在且是绝对路径）
    Returns:
        json格式字符串：
        {
            "success": 操作成功为True,失败为False
            "message": 操作概要
        }
    """
    try:
        src = resolve_safe_path(src)
    except SecurityException as e:
        return json.dumps({
            "success": False,
            "message": str(e)
        }, ensure_ascii=False, indent=2)

    try:
        dst = resolve_safe_path(dst)
    except SecurityException as e:
        return json.dumps({
            "success": False,
            "message": str(e)
        }, ensure_ascii=False, indent=2)

    result = {"success": False, "message": ""}

    #如果src不存在或不是目录
    if not os.path.isdir(src):
        typer.echo(typer.style(f"[ERROR]源目录：{src}不存在或不是目录",fg=typer.colors.RED))
        result["message"] = f"源目录：{src}不存在或不是目录"
        return json.dumps(result, ensure_ascii=False, indent=2)

    # 如果dst不存在或不是目录
    if not os.path.isdir(dst):
        typer.echo(typer.style(f"[ERROR]目标路径不存在或不为目录：{dst}", fg=typer.colors.RED))
        result["message"] = f"目标路径不存在或不为目录：{dst}"
        return json.dumps(result, ensure_ascii=False, indent=2)

    try:
        typer.echo(typer.style(f"[执行中]正在将源目录：{src} 复制到 {dst} 目录下...",fg=typer.colors.WHITE))
        shutil.copytree(src, os.path.join(dst, os.path.basename(src)), dirs_exist_ok=True)
        typer.echo(typer.style(f"[Success]复制成功！",fg=typer.colors.GREEN))
        result["success"] = True
        result["message"] = "复制成功"
        return json.dumps(result, ensure_ascii=False, indent=2)
    except shutil.SameFileError as e:
        typer.echo(typer.style(f"[ERROR]源和目标指向同一个目录 ({src})，未执行复制：{e}", fg=typer.colors.RED))
        result["message"] = f"错误: 源和目标指向同一个目录 ({src})，未执行复制：{e}"
        return json.dumps(result, ensure_ascii=False, indent=2)
    except PermissionError as e:
        typer.echo(typer.style(f"[ERROR]权限不足，复制失败：{e}", fg=typer.colors.RED))
        result["message"] = f"权限不足，复制失败：{e}"
        return json.dumps(result, ensure_ascii=False, indent=2)
    except OSError as e:
        typer.echo(typer.style(f"[ERROR]未知错误：{e}", fg=typer.colors.RED))
        result["message"] = f"未知错误：{e}"
        return json.dumps(result, ensure_ascii=False, indent=2)
