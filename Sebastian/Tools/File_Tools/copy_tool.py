import shutil
import json
import typer
import os
from agents import function_tool

@function_tool
def cp_file(src: str, dst: str)->str:
    """
    复制文件到目标路径
    Args:
        src: 源文件名称（必须是绝对路径）
        dst: 目标路径（必须是绝对路径）
    Returns:
        json字符串：{"success": bool, "message": str}
    """
    result = {"success": False, "message": ""}
    #源文件是否存在
    if not os.path.exists(src):
        typer.echo(typer.style(f"[ERROR]源文件：{src}不存在",fg=typer.colors.RED))
        result["message"] = f"源文件：{src}不存在"
        return json.dumps(result, ensure_ascii=False, indent=2)

    #源文件是否是文件
    if not os.path.isfile(src):
        typer.echo(typer.style(f"[ERROR]源文件：{src}不是文件",fg=typer.colors.RED))
        result["message"] = f"源文件：{src}不是文件"
        return json.dumps(result, ensure_ascii=False, indent=2)

    #如果dst是文件，直接拒绝
    if os.path.isfile(dst):
        typer.echo(typer.style(f"[ERROR]目标路径已存在且为文件：{dst}",fg=typer.colors.RED))
        result["message"] = f"目标路径已存在且为文件：{dst}"
        return json.dumps(result, ensure_ascii=False)

    #如果dst不存在
    if not os.path.exists(dst):
        confirmed = typer.confirm(typer.style(f"目标路径：{dst}不存在，是否创建？",fg=typer.colors.YELLOW))
        if not confirmed:
            typer.echo("已终止本次操作")
            result["message"] = f"用户明确终止了本次操作，不用再询问第二次了"
            return json.dumps(result, ensure_ascii=False, indent=2)
        try:
            os.makedirs(dst)
            typer.echo(typer.style(f"[执行中]已创建路径：{dst}",fg=typer.colors.WHITE))
        except FileExistsError as e:
            typer.echo(typer.style(f"[ERROR]目标目录:{dst}已经存在：{e}",fg=typer.colors.RED))
            result["message"] = f"目标目录:{dst}已经存在：{e}"
            return json.dumps(result, ensure_ascii=False, indent=2)
        except OSError as e:
            typer.echo(typer.style(f"[ERROR]未知错误：{e}",fg=typer.colors.RED))
            result["message"] = f"未知错误：{e}"
            return json.dumps(result, ensure_ascii=False, indent=2)

    try:
        typer.echo(typer.style(f"[执行中]正在将源文件：{src} 复制到 {dst} 目录下...",fg=typer.colors.WHITE))
        shutil.copy2(src, dst)
        typer.echo(typer.style(f"[执行中]复制成功！",fg=typer.colors.WHITE))
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
def cp_dict(src: str, dst: str):
    """
    递归复制整个目录到目标路径
    Args:
        src: 源目录名称（必须是绝对路径）
        dst: 目标路径（必须是绝对路径）
    Returns:
        json字符串：{"success": bool, "message": str}
    """
    result = {"success": False, "message": ""}
    #源目录是否存在
    if not os.path.exists(src):
        typer.echo(typer.style(f"[ERROR]源目录：{src}不存在",fg=typer.colors.RED))
        result["message"] = f"源目录：{src}不存在"
        return json.dumps(result, ensure_ascii=False, indent=2)

    #源目录是否是目录
    if not os.path.isdir(src):
        typer.echo(typer.style(f"[ERROR]源目录：{src}不是目录",fg=typer.colors.RED))
        result["message"] = f"源目录：{src}不是目录"
        return json.dumps(result, ensure_ascii=False, indent=2)

    # 如果dst是文件，直接拒绝
    if os.path.isfile(dst):
        typer.echo(typer.style(f"[ERROR]目标路径已存在且为文件：{dst}", fg=typer.colors.RED))
        result["message"] = f"目标路径已存在且为文件：{dst}"
        return json.dumps(result, ensure_ascii=False)

    #如果dst不存在
    if not os.path.exists(dst):
        confirmed = typer.confirm(typer.style(f"目标路径：{dst}不存在，是否创建？",fg=typer.colors.YELLOW))
        if not confirmed:
            typer.echo("已终止本次操作")
            result["message"] = f"用户明确终止了本次操作，不用再询问第二次了"
            return json.dumps(result, ensure_ascii=False, indent=2)
        try:
            os.makedirs(dst)
            typer.echo(typer.style(f"[执行中]已创建路径：{dst}",fg=typer.colors.WHITE))
        except FileExistsError as e:
            typer.echo(typer.style(f"[ERROR]目标目录:{dst}已经存在：{e}",fg=typer.colors.RED))
            result["message"] = f"目标目录:{dst}已经存在：{e}"
            return json.dumps(result, ensure_ascii=False, indent=2)
        except OSError as e:
            typer.echo(typer.style(f"[ERROR]未知错误：{e}",fg=typer.colors.RED))
            result["message"] = f"未知错误：{e}"
            return json.dumps(result, ensure_ascii=False, indent=2)

    try:
        typer.echo(typer.style(f"[执行中]正在将源目录：{src} 复制到 {dst} 目录下...",fg=typer.colors.WHITE))
        shutil.copytree(src, os.path.join(dst, os.path.basename(src)), dirs_exist_ok=True)
        typer.echo(typer.style(f"[执行中]复制成功！",fg=typer.colors.WHITE))
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
