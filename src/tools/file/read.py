import os
import json
from src.security.path_safety import resolve_safe_path
from src.utils.exceptions import SecurityException
from src.tools.tools_registry import get_tools_registry


def read_file(path: str, filename: str) -> str:
    if filename.endswith(".pdf"):
        return json.dumps(
            {
                "success": False,
                "summary": "不支持读取pdf文档操作，请使用 read_pdf 工具",
                "content": None
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
                "summary": str(e),
                "content": None
            },
            ensure_ascii=False
        )
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return json.dumps(
            {
                "success": True,
                "summary": f"成功读取文件 {file_path}",
                "content": content
            },
            ensure_ascii=False
        )
    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "summary": str(e),
                "content": None
            },
            ensure_ascii=False
        )


READ_FILE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "读取文本文件内容。注意：PDF文件请使用 read_pdf 工具。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "父目录绝对路径，如 /home/user/docs/"},
                "filename": {"type": "string", "description": "文件名（含扩展名），如 note.txt"},
            },
            "required": ["path", "filename"],
        },
    },
}

get_tools_registry().register_tool("read_file", read_file, READ_FILE_SCHEMA, for_agent="File_Agent")
