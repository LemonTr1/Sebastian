import subprocess
import json

import typer
from agents import function_tool

@function_tool
def execute_local_shell(command: str, timeout: int = 30)->str:
    """
    在本机中执行Shell命令（极度危险，执行前必须先在沙箱环境中执行并分析执行结果以及危害性并告知用户，得到用户授权后才可以执行）
    Args:
        command: shell命令
        timeout: 超时时间限制
    Returns:
        json字符串，里面包含了执行结果和返回信息
    """

    typer.echo(typer.style(f"[执行中]正在终端执行命令：{command[:15]}...",fg=typer.colors.WHITE))
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
            "output": result.stdout +result.stderr,
            "exit_code": result.returncode
        })
    except subprocess.TimeoutExpired:
        return json.dumps({"success": False, "error": "Command timed out"})
