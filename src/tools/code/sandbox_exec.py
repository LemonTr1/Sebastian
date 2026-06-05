import os
import json
from src.security.command_guard import security_guard
from src.utils.exceptions import SecurityException
from src.sandbox.bubblewrap import BubblewrapSandbox

TIMEOUT = 60

def execute_in_sandbox(command: str, code_file_path: str = "") -> str:
    try:
        security_guard(command)
    except SecurityException as e:
        return json.dumps(
            {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "error": str(e)
            },
            ensure_ascii=False
        )

    mount_paths = []
    if code_file_path and os.path.exists(code_file_path):
        home = os.path.expanduser("~")
        abs_path = os.path.abspath(code_file_path)
        if not abs_path.startswith(home):
            return json.dumps(
                {
                    "success": False,
                    "stdout": "",
                    "stderr": "code_file_path必须在家目录下",
                    "error": "path error"
                },
                ensure_ascii=False
            )
        sandbox_path = "/workspace/" + os.path.basename(abs_path)
        if os.path.isdir(abs_path):
            mount_paths.append((abs_path, sandbox_path, False))
        else:
            parent = os.path.dirname(abs_path)
            mount_paths.append((parent, "/workspace", False))

    sandbox = BubblewrapSandbox()
    try:
        result = sandbox.run(command, mount_paths=mount_paths, timeout=TIMEOUT)
        return json.dumps(
            {
                "success": result["success"],
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "returncode": result["returncode"]
            },
            ensure_ascii=False
        )
    finally:
        sandbox.cleanup()


SANDBOX_EXEC_SCHEMA = {
    "type": "function",
    "function": {
        "name": "execute_in_sandbox",
        "description": "【默认工具】在bubblewrap隔离沙箱中安全执行代码或命令。任何代码文件(.py/.sh/.c/.java/.js等)、用户提供的脚本、不熟悉的命令，都必须使用此工具。大部分代码执行任务默认选此工具。",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要在沙箱中执行的命令或代码"},
                "code_file_path": {"type": "string", "description": "可选，要挂载到沙箱的代码文件或目录的绝对路径（必须在家目录下），留空则不挂载额外路径"},
            },
            "required": ["command"],
        },
    },
}
