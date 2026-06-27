import os
import json
from src.security.path_safety import resolve_safe_path
from src.utils.exceptions import SecurityException
from src.tools.tools_registry import get_tools_registry


def ls(path: str) -> str:
    try:
        path = resolve_safe_path(path, "real")
    except SecurityException as e:
        return json.dumps(
            {
                "success": False,
                "file_list": [],
                "error": str(e)
            },
            ensure_ascii=False
        )
    if not os.path.isdir(path):
        return json.dumps(
            {
                "success": False,
                "file_list": [],
                "error": f"{path} 不是有效目录"
            },
            ensure_ascii=False
        )
    try:
        listed = os.listdir(path)
        return json.dumps(
            {
                "success": True,
                "file_list": listed,
                "error": None
            },
            ensure_ascii=False
        )
    except PermissionError as e:
        return json.dumps(
            {
                "success": False,
                "file_list": [],
                "error": f"权限不足: {e}"
            },
            ensure_ascii=False
        )
    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "file_list": [],
                "error": str(e)
            },
            ensure_ascii=False
        )


LS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "ls",
        "description": "列出指定目录下的所有文件和子目录",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "要列出的目录绝对路径"},
            },
            "required": ["path"],
        },
    },
}

get_tools_registry().register_tool("ls", ls, LS_SCHEMA, for_agent="File_Agent")
