import json
from src.logs.app_log import get_log
from src.security.command_guard import security_guard
from src.utils.exceptions import SecurityException
from src.sandbox.bubblewrap import BubblewrapSandbox
from src.tools.tools_registry import get_tools_registry

TIMEOUT = 180

logger = get_log()

def bash(command: str, run_in_background: bool = False) -> str:
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

    try:
        sandbox = BubblewrapSandbox()
        result = sandbox.run(command)
        return json.dumps(
            {
                "success": result["success"],
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "returncode": result["returncode"]
            },
            ensure_ascii=False
        )
    except RuntimeError as e:
        logger.error(f"bubblewrap无法使用：{str(e)}")
        return json.dumps({
            "success": False,
            "error": f"bubblewrap无法使用：{str(e)}",
        }, ensure_ascii=False)
    except FileNotFoundError as e:
        logger.error(f"沙箱配置文件加载失败：{str(e)}")
        return json.dumps({
            "success": False,
            "error": f"沙箱配置文件加载失败：{str(e)}",
        }, ensure_ascii=False)
    except json.JSONDecodeError as e:
        logger.error(f"沙箱配置文件解析失败：{str(e)}")
        return json.dumps({
            "success": False,
            "error": f"沙箱配置文件解析失败：{str(e)}",
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f"沙箱初始化失败：{str(e)}")
        return json.dumps({
            "success": False,
            "error": f"沙箱初始化失败: {str(e)}",
        }, ensure_ascii=False)


BASH_SCHEMA = {
    "type": "function",
    "function": {
        "name": "bash",
        "description": "Execute arbitrary shell commands in a sandboxed environment. This is the most powerful and flexible tool — use it for operations that have no dedicated structured tool equivalent. 【此工具需要用户确认后方可执行】",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "执行的命令或代码"},
                "run_in_background": {"type": "boolean", "description": "可选，是否在后台以异步方式运行，true表示以异步方式运行，默认为false"},
            },
            "required": ["command"],
        },
    },
}

#注册工具
get_tools_registry().register_tool("bash", bash, BASH_SCHEMA, hitl=True, for_agent="Brain_Agent")
