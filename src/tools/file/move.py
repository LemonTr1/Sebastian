import os
import shutil
import json
from src.security.path_safety import resolve_safe_path
from src.utils.exceptions import SecurityException
from src.tools.tools_registry import get_tools_registry


def move_file(src: str, dst: str) -> str:
    try:
        dst = resolve_safe_path(dst)
    except SecurityException as e:
        return json.dumps(
            {
                "success": False,
                "summary": str(e)
            },
            ensure_ascii=False
        )
    if not os.path.isdir(dst):
        return json.dumps(
            {
                "success": False,
                "summary": f"目标 {dst} 必须是目录"
            },
            ensure_ascii=False
        )
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
    try:
        shutil.move(src, dst)
        return json.dumps(
            {
                "success": True,
                "summary": f"移动成功: {src} -> {dst}/"
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


MOVE_FILE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "move_file",
        "description": "将文件或目录移动到目标目录下。【此工具需要用户确认后方可执行】",
        "parameters": {
            "type": "object",
            "properties": {
                "src": {"type": "string", "description": "源文件/目录绝对路径"},
                "dst": {"type": "string", "description": "目标目录绝对路径（必须是已存在的目录）"},
            },
            "required": ["src", "dst"],
        },
    },
}

get_tools_registry().register_tool("move_file", move_file, MOVE_FILE_SCHEMA, hitl=True, for_agent="File_Agent")
