import typer
import os
from agents import function_tool
from src.Interfaces.SafePath import resolve_safe_path
from src.Interfaces.Exception.SecurityException import SecurityException
import json

@function_tool
def edit(path: str, filename: str, context: str)->str:
    """
    编辑/修改文件内容（编辑docx文档使用modify_docx工具）
    Args:
        path: str类型，父目录路径字符串（必须为绝对路径）
        filename: str类型，文件名（包含扩展名）
        context: str类型，待写入的文本内容（会覆盖掉原来的文本内容）
    Returns:
        json结构字符串
        {
            "success": 编辑/修改成功为True，失败为False,
            "summary": 操作摘要
        }
    """
    if filename.endswith(".docx"):
        return json.dumps({
            "success": False,
            "summary": "必须使用modify_docx编辑.docx文档"
        }, ensure_ascii=False, indent=2)

    path = os.path.abspath(path)
    file_path = os.path.join(path, filename)
    try:
        file_path = resolve_safe_path(file_path)
    except SecurityException as e:
        return json.dumps({
            "success": False,
            "summary": str(e)
        }, ensure_ascii=False, indent=2)
    confirmed = typer.confirm(typer.style(f"[Warn]你确定要修改文件{file_path}的内容吗", fg=typer.colors.YELLOW))
    if not confirmed:
        typer.echo("已终止本次操作")
        return json.dumps({
            "success": False,
            "summary": "用户已终止本次操作"
        }, ensure_ascii=False, indent=2)
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(context)
        return json.dumps({
            "success": True,
            "summary": "修改文件内容成功"
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "summary": f"发生错误{str(e)}"
        }, ensure_ascii=False, indent=2)

