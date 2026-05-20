import os
import typer
from agents import function_tool
import json
from src.Interfaces.Exception.SecurityException import SecurityException
from src.Interfaces.Resolver.SafePathResolver import resolve_safe_path

@function_tool
def rename(src: str, new_name: str) -> str:
    """
    重命名文件/目录。
    Args:
        src: str类型，源路径（文件或目录，必须为绝对路径）
        new_name: str类型，新的名称（仅文件或目录名，不包含路径）
    Returns:
        json形式的字符串
        {
            "success": 操作成功为True，失败为False,
            "summary": 操作概要
        }
    """
    try:
        src = resolve_safe_path(src)
    except SecurityException as e:
        typer.echo(typer.style(f"{e}", fg=typer.colors.RED))
        return json.dumps({
            "success": False,
            "summary": str(e)
        }, ensure_ascii=False, indent=2)
    parent_path = os.path.dirname(src)
    target_path = os.path.join(parent_path, new_name)

    # 初始确认
    confirmed = typer.confirm(
        typer.style(f"[Warn] 确定将 '{src}' 重命名为 '{target_path}' 吗？", fg=typer.colors.YELLOW)
    )
    if not confirmed:
        typer.echo("用户已取消该操作")
        return json.dumps({
            "success": False,
            "summary": "用户确认取消本次操作"
        }, ensure_ascii=False, indent=2)

    try:
        os.rename(src, target_path)
        return json.dumps({
            "success": True,
            "summary": f"成功将 '{src}' 重命名为 '{target_path}'"
        },ensure_ascii=False, indent=2)
    except PermissionError as e:
        return json.dumps({
            "success": False,
            "summary": f"权限不足：{str(e)}"
        }, ensure_ascii=False, indent=2)
    except OSError as e:
        return json.dumps({
            "success": False,
            "summary": f"系统出现错误：{str(e)}"
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "summary": f"出现错误：{str(e)}"
        }, ensure_ascii=False, indent=2)

