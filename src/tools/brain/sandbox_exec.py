import os
import json
from src.security.command_guard import security_guard
from src.utils.exceptions import SecurityException
from src.sandbox.bubblewrap import BubblewrapSandbox
from src.tools.tools_registry import get_tools_registry
from src.utils.load_prompt import get_prompt_loader

TIMEOUT = 180

def execute_in_sandbox(command: str, code_file_path: str = "", ro: bool = True, run_in_background: bool = False) -> str:
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
            mount_paths.append((abs_path, sandbox_path, ro))
        else:
            parent = os.path.dirname(abs_path)
            mount_paths.append((parent, "/workspace", ro))

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
        "description": f"{get_prompt_loader().load_prompt('execute_in_sandbox')}",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要在沙箱中执行的命令或代码"},
                "code_file_path": {"type": "string", "description": "可选，要挂载到沙箱的代码文件或目录的绝对路径（必须在家目录下），留空则不挂载额外路径，挂载到沙箱内路径为/workspace"},
                "ro": {"type": "boolean", "description": "可选，是否以只读方式挂载代码文件或目录，true为只读，false为可读写挂载，默认为true"},
                "run_in_background": {"type": "boolean", "description": "可选，是否在后台以异步方式运行，true表示以异步方式运行，默认为false"},
            },
            "required": ["command"],
        },
    },
}

#注册工具
get_tools_registry().register_tool("execute_in_sandbox", execute_in_sandbox, SANDBOX_EXEC_SCHEMA, hitl=True, for_agent="Brain_Agent")
