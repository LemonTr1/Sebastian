import os
import json
from src.utils.path_policy import resolve_path
from src.utils.exceptions import SecurityException
from src.tools.tools_registry import get_tools_registry
from src.utils.load_prompt import get_prompt_loader


def ls(path: str) -> str:
    try:
        path = resolve_path(path)
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
        "description": get_prompt_loader().load_tool_manual("ls"),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "要列出的目录绝对路径"},
            },
            "required": ["path"],
        },
    },
}

get_tools_registry().register_tool("ls", ls, LS_SCHEMA, for_agent="Brain_Agent")
