import json
from src.logs.app_log import get_log
from src.sandbox import create_sandbox
from src.tools.tools_registry import get_tools_registry
from src.utils.load_prompt import get_prompt_loader

TIMEOUT = 180

logger = get_log()

def bash(command: str, description: str, run_in_background: bool = False) -> str:
    try:
        sandbox = create_sandbox()
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
        logger.error(f"沙箱无法使用：{str(e)}")
        return json.dumps({
            "success": False,
            "error": f"沙箱无法使用：{str(e)}",
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
        "description": get_prompt_loader().load_tool_manual("bash"),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "执行的命令或代码"},
                "description": {"type": "string", "description": "用自然语言描述命令的功能和目的"},
                "run_in_background": {"type": "boolean", "description": "可选，是否在后台以异步方式运行，true表示以异步方式运行，默认为false"},
            },
            "required": ["command", "description"],
        },
    },
}

#注册工具
get_tools_registry().register_tool("bash", bash, BASH_SCHEMA, hitl=True, for_agent="Brain_Agent")
