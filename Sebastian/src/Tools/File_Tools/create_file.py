import os
import typer
from agents import function_tool
from src.Interfaces.Resolver.SafePathResolver import resolve_safe_path
from src.Interfaces.Exception.SecurityException import SecurityException
import json

@function_tool
def create_file(path: str, filename: str)->str:
    """
    在指定路径下建立新的空文件（创建.docx文档使用create_docx工具）
    Args:
        path: str类型，表示父目录路径（若不存在，可交互确认后自动创建）
        filename: str类型，表示文件名（包含扩展名）
    Returns:
        json结构字符串 {
            "success"：操作成功为True，失败为False,
            "summary"：操作概要
        }
    """
    if filename.endswith(".docx"):
        return json.dumps({
            "success": False,
            "summary": "必须使用create_docx创建.docx文档"
        }, ensure_ascii=False, indent=2)

    try:
        path = resolve_safe_path(path)
    except SecurityException as e:
        return json.dumps({
            "success": False,
            "summary": str(e)
        }, ensure_ascii=False, indent=2)

    if os.path.isfile(path):
        typer.echo(typer.style(f"[ERROR]父路径{path}已存在且为文件，无法在其中创建文件",fg=typer.colors.RED))
        return json.dumps({
            "success": False,
            "summary": f"父路径{path}已存在且为文件，无法在其中创建文件，请求创建新目录{path}",
        }, ensure_ascii=False, indent=2)

    #拼接完整路径
    file_path = os.path.join(path, filename)

    if not os.path.exists(path):
        return json.dumps({
            "success": False,
            "summary": f"路径目录{path}不存在，请求是否同意创建路径目录{path}",
        }, ensure_ascii=False, indent=2)

    if os.path.exists(file_path):
        confirmed = typer.confirm(typer.style(f"[Warn]文件{file_path}已经存在，覆盖会清空内容，确定吗",fg=typer.colors.YELLOW))
        if not confirmed:
            return json.dumps({
                "success": False,
                "summary": f"用户确认停止该操作",
            }, ensure_ascii=False, indent=2)

    try:
        #创建空文件
        with open(file_path, 'w') as f:
            pass
        typer.echo(typer.style(f"[Success]文件{file_path}已创建/覆盖", fg=typer.colors.GREEN))
        return json.dumps({
            "success": True,
            "summary": f"新文件创建成功！{file_path}已创建/覆盖",
        }, ensure_ascii=False, indent=2)
    except OSError as e:
        typer.echo(typer.style(f"[Error] 创建文件 {file_path} 失败: {e}", fg=typer.colors.RED))
        return json.dumps({
            "success": False,
            "summary": f"创建文件{file_path}失败",
        }, ensure_ascii=False, indent=2)

