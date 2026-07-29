import shutil
import json
from src.tools.tools_registry import get_tools_registry


def which(command: str) -> str:
    path = shutil.which(command)
    if path:
        return json.dumps(
            {
                "success": True,
                "summary": f"命令 {command} 位于 {path}",
                "path": path
            },
            ensure_ascii=False
        )
    return json.dumps(
        {
            "success": False,
            "summary": f"未找到命令: {command}",
            "path": None
        },
        ensure_ascii=False
    )


WHICH_SCHEMA = {
    "type": "function",
    "function": {
        "name": "which",
        "description": "查看指定路径是否存在，类似于 Linux 的 which 命令",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要查看的路径"},
            },
            "required": ["command"],
        },
    },
}

get_tools_registry().register_tool("which", which, WHICH_SCHEMA, for_agent="Brain_Agent")
