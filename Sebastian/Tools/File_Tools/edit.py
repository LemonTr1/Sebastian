import typer
import os
from agents import function_tool
from pathlib import Path

HOME = Path.home()

@function_tool
def edit(path: str, filename: str, context: str)->dict:
    """
    编辑/修改文件内容
    Args:
        path: 父目录路径字符串（必须为绝对路径）
        filename: 文件名（包含扩展名）
        context: 待写入的文本内容（会覆盖掉原来的文本内容）
    Returns:
        结构化字典 {
            "success": 编辑/修改成功为True，失败为False,
            "summary": 操作摘要
        }
    """
    path = os.path.abspath(path)
    if not Path(path).is_relative_to(HOME):
        return {
            "success": False,
            "summary": f"操作必须在{str(HOME)}目录下"
        }
    file_path = os.path.join(path, filename)
    confirmed = typer.confirm(typer.style(f"[Warn]你确定要修改文件{file_path}的内容吗", fg=typer.colors.YELLOW))
    if not confirmed:
        typer.echo("已终止本次操作")
        return {
            "success": False,
            "summary": "用户已终止本次操作"
        }
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(context)
        return {
            "success": True,
            "summary": "修改文件内容成功"
        }
    except Exception as e:
        return {
            "success": False,
            "summary": f"发生错误{str(e)}"
        }

