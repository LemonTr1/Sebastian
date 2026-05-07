import subprocess
import json

import typer
from agents import function_tool

@function_tool
def execute_local_shell(command: str, timeout: int = 30)->str:
    """
    在当前系统中执行Shell命令（注意：用户提供的或未知外来的Shell代码必须先在Shell沙箱中运行）
    Args:
        command: shell命令
        timeout: 超时时间限制
    Returns:
        json字符串，里面包含了执行结果和返回信息
    """
    #命令黑名单
    FORBIDDEN_COMMANDS = ["git", "rm", "which", "ls", "cp", "mv", "mkdir", "chmod", "cd"]
    if any(command.strip().startswith(cmd) for cmd in FORBIDDEN_COMMANDS):
        return json.dumps({"success": False, "error": "Error: 该命令被禁止，请使用专用工具（如 Git_Agent_Tool或File_Agent_Tool）"})

    typer.echo(typer.style(f"[执行中]正在终端执行命令：{command[:20]}...",fg=typer.colors.WHITE))
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return json.dumps({
            "success": result.returncode == 0,
            "output": result.stdout+result.stderr,
            "exit_code": result.returncode
        })
    except subprocess.TimeoutExpired:
        return json.dumps({"success": False, "error": "Command timed out"})
