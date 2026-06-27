import os
import json
from src.security.path_safety import resolve_safe_path
from src.utils.exceptions import SecurityException
from src.tools.tools_registry import get_tools_registry


def rename_file(src: str, new_name: str) -> str:
    try:
        src = resolve_safe_path(src)
    except SecurityException as e:
        return json.dumps(
            {
                "success": False,
                "summary": str(e)
            },
            ensure_ascii=False
        )
    parent = os.path.dirname(src)
    target = os.path.join(parent, new_name)
    try:
        os.rename(src, target)
        return json.dumps(
            {
                "success": True,
                "summary": f"重命名: {src} -> {target}"
            },
            ensure_ascii=False
        )
    except PermissionError as e:
        return json.dumps(
            {
                "success": False,
                "summary": f"权限不足: {e}"
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


RENAME_FILE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "rename_file",
        "description": "重命名文件或目录。【此工具需要用户确认后方可执行】",
        "parameters": {
            "type": "object",
            "properties": {
                "src": {"type": "string", "description": "源文件/目录绝对路径"},
                "new_name": {"type": "string", "description": "新名称（仅名称，不含目录部分）"},
            },
            "required": ["src", "new_name"],
        },
    },
}

get_tools_registry().register_tool("rename_file", rename_file, RENAME_FILE_SCHEMA, hitl=True, for_agent="File_Agent")
