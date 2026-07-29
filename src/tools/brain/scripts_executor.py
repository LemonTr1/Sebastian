from pathlib import Path
import json
import subprocess
import os
import stat
from src.tools.tools_registry import get_tools_registry

BASE_DIR = Path.home() / ".sebastian" / "skills"

#供Agent使用的工具接口
def execute_script(script_path: str, parameters: list, timeout: int = 20) -> str:
    if not Path(script_path).is_relative_to(BASE_DIR) or Path(script_path).parent.name != "scripts":
        return json.dumps({
            "success": False,
            "error": f"可执行脚本路径必须在 {BASE_DIR} 目录下，并且其父目录名必须为`scripts`"
        }, ensure_ascii=False)

    if not Path(script_path).is_file():
        return json.dumps({
            "success": False,
            "error": f"脚本不存在: {script_path}"
        }, ensure_ascii=False)

    if parameters is None:
        parameters = []

    # 检查并添加Agent执行权限
    if not os.access(script_path, os.X_OK):
        try:
            os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        except PermissionError:
            return json.dumps({
                "success": False,
                "error": "无法添加执行权限，告诉用户手动运行: chmod +x " + str(script_path)
            }, ensure_ascii=False)

    try:
        result = subprocess.run(
            ["bash", str(script_path)] + parameters,
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout
        )

        return json.dumps({
            "success": True,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip()
        }, ensure_ascii=False)

    except subprocess.CalledProcessError as e:
        # 捕获 check=True 抛出的异常
        return json.dumps({
            "success": False,
            "error": e.stderr.strip() if e.stderr else f"脚本退出码: {e.returncode}"
        }, ensure_ascii=False)

    except subprocess.TimeoutExpired:
        return json.dumps({
            "success": False,
            "error": "Script execution timed out."
        }, ensure_ascii=False)

    except PermissionError:
        return json.dumps({
            "success": False,
            "error": "权限不足，无法执行脚本"
        }, ensure_ascii=False)

    except FileNotFoundError:
        return json.dumps({
            "success": False,
            "error": f"脚本文件不存在: {script_path}"
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"执行脚本时发生错误: {str(e)}"
        }, ensure_ascii=False)

SCRIPT_REGISTRY_SCHEMA = {
    "type": "function",
    "function": {
        "name": "execute_script",
        "description": "执行指定的脚本，并返回结果。",
        "parameters": {
            "type": "object",
            "properties": {
                "script_path": {
                    "type": "string",
                    "description": "要执行的脚本，必须精确匹配已注册的脚本名称，必须使用绝对路径",
                },
                "parameters": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "传递给脚本的参数列表，不需要传参则传递空数组",
                },
            },
            "required": ["script_path", "parameters"],
        },
    },
}

#注册工具
get_tools_registry().register_tool("execute_script", execute_script, SCRIPT_REGISTRY_SCHEMA, for_agent="Brain_Agent")


