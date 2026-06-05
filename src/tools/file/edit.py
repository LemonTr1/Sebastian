import os
import json
from src.security.path_safety import resolve_safe_path
from src.utils.exceptions import SecurityException


def edit_file(path: str, filename: str, content: str) -> str:
    if filename.endswith(".pdf"):
        return json.dumps(
            {
                "success": False,
                "summary": "不支持编辑PDF文件, 请使用 read_pdf 读取"
            },
            ensure_ascii=False
        )
    path = os.path.abspath(path)
    file_path = os.path.join(path, filename)
    try:
        file_path = resolve_safe_path(file_path)
    except SecurityException as e:
        return json.dumps(
            {
                "success": False,
                "summary": str(e)
            },
            ensure_ascii=False
        )
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return json.dumps(
            {
                "success": True,
                "summary": f"文件 {file_path} 内容已更新"
            },
            ensure_ascii=False
        )
    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "summary": str(e)
            },
            ensure_ascii=False
        )


EDIT_FILE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "edit_file",
        "description": "编辑/覆盖文件内容。此操作将完全替换文件原有内容为新内容。【此工具需要用户确认后方可执行】",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "父目录绝对路径，如 /home/user/docs/"},
                "filename": {"type": "string", "description": "文件名（含扩展名）"},
                "content": {"type": "string", "description": "要写入的新内容（完全替换）"},
            },
            "required": ["path", "filename", "content"],
        },
    },
}
