import os
import json
from src.security.path_safety import resolve_safe_path
from src.utils.exceptions import SecurityException


def mkdir(path: str, folder: str) -> str:
    try:
        path = resolve_safe_path(path)
    except SecurityException as e:
        return json.dumps(
            {
                "success": False,
                "summary": str(e)
            },
            ensure_ascii=False
        )
    dir_path = os.path.join(path, folder)
    if os.path.isdir(dir_path):
        return json.dumps(
            {
                "success": False,
                "summary": f"目录已存在: {dir_path}"
            },
            ensure_ascii=False
        )
    try:
        os.makedirs(dir_path, exist_ok=True)
        return json.dumps(
            {
                "success": True,
                "summary": f"目录创建成功: {dir_path}"
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


MKDIR_SCHEMA = {
    "type": "function",
    "function": {
        "name": "mkdir",
        "description": "在指定路径下创建新目录",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "父目录绝对路径"},
                "folder": {"type": "string", "description": "要创建的目录名称"},
            },
            "required": ["path", "folder"],
        },
    },
}
