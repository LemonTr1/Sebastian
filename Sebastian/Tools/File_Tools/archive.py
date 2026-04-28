import shutil
import os
import json

import typer
from agents import function_tool

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
        source_path: 源文件夹完整路径，如 "/home/user/projects"
        output_path: 输出文件基础路径，如 "/backup/projects_backup"
        archive_format: zip/tar/gztar/bztar/xztar
    Returns:
        json形式的字符串：
        {
            "success": bool, #压缩是否成功
            "message": str,
            "output_file": str | None  # 实际生成的文件路径
        }
    """
    result = {"success": False, "message": "", "output_file": None}

    if not os.path.exists(source_path):
        typer.echo(typer.style(f"[ERROR]源路径不存在：{source_path}",fg=typer.colors.RED))
        result["message"] = f"源路径不存在: {source_path}"
        return json.dumps(result, ensure_ascii=False, indent=2)

    if not os.path.isdir(source_path):
        typer.echo(typer.style(f"[ERROR]源路径不是目录：{source_path}",fg=typer.colors.RED))
        result["message"] = f"源路径不是目录: {source_path}"
        return json.dumps(result, ensure_ascii=False, indent=2)

    # 自动拆分 root_dir 和 base_dir
    source_path = os.path.abspath(source_path)
    root_dir = os.path.dirname(source_path)
    base_dir = os.path.basename(source_path)

    try:
        typer.echo(typer.style(f"[执行中]正在压缩{source_path}",fg=typer.colors.WHITE))
        output_file = shutil.make_archive(
            base_name=output_path,
            format=archive_format,
            root_dir=root_dir,
            base_dir=base_dir
        )
        result["success"] = True
        result["message"] = f"压缩成功: {output_file}"
        result["output_file"] = output_file

    except ValueError as e:
        typer.echo(typer.style(f"[ERROR]格式错误",fg=typer.colors.RED))
        result["message"] = f"格式错误: {e}"
    except PermissionError:
        typer.echo(typer.style(f"[ERROR]权限不足，无法写入：{output_path}",fg=typer.colors.RED))
        result["message"] = f"权限不足，无法写入: {output_path}"
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
        archive_path: 压缩包路径
        extract_dir: 解压目标目录（默认当前目录）
        format: 可选，zip/tar/gztar/bztar/xztar
    Returns:
        JSON 字符串: {"success": bool, "message": str, "extract_dir": str|null}
    """
    result = {"success": False, "message": "", "extract_dir": None}

    if not os.path.exists(archive_path):
        typer.echo(typer.style(f"[ERROR]压缩包不存在：{archive_path}",fg=typer.colors.RED))
        result["message"] = f"压缩包不存在: {archive_path}"
        return json.dumps(result, ensure_ascii=False, indent=2)

    try:
        shutil.unpack_archive(archive_path, extract_dir, format)
        result["success"] = True
        result["message"] = f"解压成功到: {os.path.abspath(extract_dir)}"
        result["extract_dir"] = os.path.abspath(extract_dir)
        typer.echo(typer.style(f"[执行中]解压成功到：{os.path.abspath(extract_dir)}",fg=typer.colors.WHITE))
    except ValueError as e:
        typer.echo(typer.style(f"[ERROR]格式错误或解压失败: {e}",fg=typer.colors.RED))
        result["message"] = f"格式错误或解压失败: {e}"
    except PermissionError:
        typer.echo(typer.style(f"[ERROR]权限不足，无法写入: {extract_dir}", fg=typer.colors.RED))
        result["message"] = f"权限不足，无法写入: {extract_dir}"
    except Exception as e:
        typer.echo(typer.style(f"[ERROR]解压失败: {type(e).__name__}: {e}", fg=typer.colors.RED))
        result["message"] = f"解压失败: {type(e).__name__}: {e}"

    return json.dumps(result, ensure_ascii=False, indent=2)