from agents import function_tool
import typer
import os
from pathlib import Path
import json
from Interface.Exception.SecurityException import SecurityException
from Interface.SafePath import resolve_safe_path

@function_tool
def read_file(path: str, filename: str)->str:
    """
    读取并以字符串形式返回目标文件内的文本内容(读取.docx或.pdf类型文件内容必须使用extract_document工具)
    Args:
        path: str类型，表示父目录路径（必须为绝对路径）
        filename: str类型，表示文件名（包含扩展名）
    Returns:
        json格式字符串 {
            "success": 表示是否成功读取到文本内容，成功为True,失败为False,
            "summary": 操作摘要
            "content": 目标文件的文本内容
        }
    """
    if filename.endswith(".docx"):
        return json.dumps({
            "success": False,
            "summary": "必须使用extract_document工具读取.docx文档或.pdf文件",
            "content": None
        }, ensure_ascii=False, indent=2)
    path = os.path.abspath(path)
    file_path = os.path.join(path, filename)

    try:
        file_path = resolve_safe_path(file_path)
    except SecurityException as e:
        return json.dumps({
            "success": False,
            "summary": str(e),
            "content": None
        }, ensure_ascii=False, indent=2)

    typer.echo(typer.style(f"[执行中]正在读取 {file_path} 的文件内容", fg=typer.colors.WHITE))
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()   # 整个文件 → 一个字符串
        return json.dumps({
            "success": True,
            "summary": f"成功读取到目标文件{file_path}的内容",
            "content": content
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "summary": f"发生错误：{str(e)}",
            "content": None
        }, ensure_ascii=False, indent=2)