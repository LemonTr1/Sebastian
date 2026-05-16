import shutil
import os
import json
import py7zr
from pathlib import Path
import typer
from agents import function_tool
from Interface.SafePath import resolve_safe_path
from Interface.Exception.SecurityException import SecurityException

#压缩
@function_tool
def make_archive(
        source_path: str,  # 要压缩的文件夹完整路径
        output_path: str,  # 输出文件路径（不含扩展名）
        archive_format: str = "zip"  # 压缩格式
) -> str:
    """
    压缩文件夹
    Args:
        source_path: str类型，源文件夹绝对路径
        output_path: str类型，输出文件绝对路径（不包含扩展名）
        archive_format: str类型，有zip/tar/gztar/bztar/xztar/7z，默认为zip
    Returns:
        json形式的字符串：
        {
            "success": 压缩成功为True,失败为False
            "message": 操作概要
        }
    """
    try:
        source_path = resolve_safe_path(source_path)
    except SecurityException as e:
        return json.dumps({
            "success": False,
            "message": str(e)
        }, ensure_ascii=False, indent=2)

    try:
        output_path = resolve_safe_path(output_path)
    except SecurityException as e:
        return json.dumps({
            "success": False,
            "message": str(e),
        }, ensure_ascii=False, indent=2)

    result = {"success": False, "message": ""}

    if not os.path.isdir(source_path):
        typer.echo(typer.style(f"[ERROR]源路径不存在或不是目录：{source_path}",fg=typer.colors.RED))
        result["message"] = f"源路径不存在或不是目录: {source_path}"
        return json.dumps(result, ensure_ascii=False, indent=2)

    if not os.path.isdir(str(Path(output_path).parent)):
        typer.echo(typer.style(f"[ERROR]目标路径不存在或不是目录", fg=typer.colors.RED))
        result["message"] = f"目标路径不存在或不是目录: {str(Path(output_path).parent)}"

    # 自动拆分 root_dir 和 base_dir
    source_path = os.path.abspath(source_path)
    root_dir = os.path.dirname(source_path)
    base_dir = os.path.basename(source_path)

    try:
        typer.echo(typer.style(f"[执行中]正在压缩{source_path}为{output_path}.{archive_format}",fg=typer.colors.WHITE))
        if archive_format != "7z":
            shutil.make_archive(
                base_name=output_path,
                format=archive_format,
                root_dir=root_dir,
                base_dir=base_dir
            )
        else:
            target = output_path + ".7z"
            with py7zr.SevenZipFile(target, "w") as archive:
                archive.writeall(source_path, arcname=Path(source_path).name)
        result["success"] = True
        result["message"] = f"压缩成功"
        typer.echo(typer.style(f"[执行中]压缩成功", fg=typer.colors.WHITE))
        return json.dumps(result, ensure_ascii=False, indent=2)
    except ValueError as e:
        typer.echo(typer.style(f"[ERROR]格式错误",fg=typer.colors.RED))
        result["message"] = f"格式错误: {e}"
        return json.dumps(result, ensure_ascii=False, indent=2)
    except PermissionError:
        typer.echo(typer.style(f"[ERROR]权限不足，无法写入：{output_path}",fg=typer.colors.RED))
        result["message"] = f"权限不足，无法写入: {output_path}"
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        typer.echo(typer.style(f"[ERROR]压缩失败",fg=typer.colors.RED))
        result["message"] = f"压缩失败: {type(e).__name__}: {e}"
        return json.dumps(result, ensure_ascii=False, indent=2)

#解压缩
@function_tool
def unpack_archive(
    archive_path: str,
    extract_dir: str = ".",
    format: str = None
) -> str:
    """
    解压文件
    Args:
        archive_path: str类型，压缩包路径（必须为绝对路径）
        extract_dir: str类型，解压目标目录（默认为当前目录，如果不是默认值的话必须为绝对路径）
        format: str类型，依据压缩包名称可选：zip/tar/gztar/bztar/xztar/7z，默认为None
    Returns:
        JSON 字符串:
        {
            "success": 操作成功为True，失败为False
            "message": 操作概要
            "extract_dir": 解压目录
        }
    """
    if extract_dir != ".":
        try:
            extract_dir = resolve_safe_path(extract_dir)
        except SecurityException as e:
            return json.dumps({
                "success": False,
                "message": str(e),
                "extract_dir": None
            }, ensure_ascii=False, indent=2)
    try:
        archive_path = resolve_safe_path(archive_path)
    except SecurityException as e:
        return json.dumps({
            "success": False,
            "message": str(e),
            "extract_dir": None
        }, ensure_ascii=False, indent=2)
    result = {"success": False, "message": "", "extract_dir": None}

    if not os.path.exists(archive_path):
        typer.echo(typer.style(f"[ERROR]压缩包不存在：{archive_path}",fg=typer.colors.RED))
        result["message"] = f"压缩包不存在: {archive_path}"
        return json.dumps(result, ensure_ascii=False, indent=2)

    try:
        typer.echo(typer.style(f"[执行中]正在解压：{archive_path}到{extract_dir}", fg=typer.colors.WHITE))
        if format != "7z":
            shutil.unpack_archive(archive_path, extract_dir, format)
        else:
            with py7zr.SevenZipFile(archive_path, "r") as archive:
                archive.extractall(extract_dir)
        result["success"] = True
        result["message"] = f"解压成功到: {os.path.abspath(extract_dir)}"
        result["extract_dir"] = os.path.abspath(extract_dir)
        typer.echo(typer.style(f"[执行中]解压成功到：{os.path.abspath(extract_dir)}",fg=typer.colors.WHITE))
        return json.dumps(result, ensure_ascii=False, indent=2)
    except ValueError as e:
        typer.echo(typer.style(f"[ERROR]格式错误或解压失败: {e}",fg=typer.colors.RED))
        result["message"] = f"格式错误或解压失败: {e}"
        return json.dumps(result, ensure_ascii=False, indent=2)
    except PermissionError:
        typer.echo(typer.style(f"[ERROR]权限不足，无法写入: {extract_dir}", fg=typer.colors.RED))
        result["message"] = f"权限不足，无法写入: {extract_dir}"
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        typer.echo(typer.style(f"[ERROR]解压失败: {type(e).__name__}: {e}", fg=typer.colors.RED))
        result["message"] = f"解压失败: {type(e).__name__}: {e}"
        return json.dumps(result, ensure_ascii=False, indent=2)


