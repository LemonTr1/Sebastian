import os
import typer
from agents import function_tool
from pathlib import Path

HOME = Path.home()

@function_tool
def rename(src: str, dst: str) -> dict:
    """
    重命名或移动文件/目录。
    Args:
        src: 源路径（文件或目录，必须为绝对路径）
        dst: 目标路径（新名称或新位置，必须为绝对路径）
    Returns:
        结构化字典：{
            "success": 操作成功为True，失败为False,
            "summary": 操作概要
        }
    """
    src = os.path.abspath(src)
    dst = os.path.abspath(dst)
    if not Path(src).is_relative_to(HOME) or not Path(dst).is_relative_to(HOME):
        return {
            "success": False,
            "summary": f"拒绝，操作必须在{str(HOME)}目录下"
        }
    # 初始确认
    confirmed = typer.confirm(
        typer.style(f"[Warn] 确定将 '{src}' 重命名为 '{dst}' 吗？", fg=typer.colors.YELLOW)
    )
    if not confirmed:
        typer.echo("用户已取消该操作")
        return {
            "success": False,
            "summary": "用户确认取消本次操作"
        }

    # 目标路径存在则再次确认
    if os.path.exists(dst):
        kind = "文件" if os.path.isfile(dst) else "目录"
        overwrite_confirmed = typer.confirm(
            typer.style(f"[Warn] 目标{kind} '{dst}' 已存在，继续将覆盖它，确定吗？", fg=typer.colors.YELLOW)
        )
        if not overwrite_confirmed:
            typer.echo("用户已取消该操作")
            return {
                "success": False,
                "summary": "用户确认取消本次操作"
            }

    try:
        os.rename(src, dst)
        msg = f"重命名成功：{src} -> {dst}"
        typer.echo(typer.style(f"[执行中] {msg}", fg=typer.colors.WHITE))
        return {
            "success": True,
            "summary": msg
        }
    except FileNotFoundError:
        typer.echo(typer.style(f"[ERROR] 源路径不存在：{src}", fg=typer.colors.RED))
        return {
            "success": False,
            "summary": f"错误：源路径不存在：{src}"
        }
    except PermissionError as e:
        typer.echo(typer.style(f"[ERROR] 没有权限：{e}", fg=typer.colors.RED))
        return {
            "success": False,
            "summary": f"错误：没有重命名权限：{e}"
        }
    except OSError as e:
        typer.echo(typer.style(f"[ERROR] 操作失败：{e}", fg=typer.colors.RED))
        return {
            "success": False,
            "summary": f"错误：重命名失败：{e}"
        }