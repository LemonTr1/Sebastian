import shutil
import json


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
        "description": "查找命令的可执行文件路径",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要查找的命令名，如 python, node"},
            },
            "required": ["command"],
        },
    },
}
