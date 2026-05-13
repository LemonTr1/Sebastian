from agents import function_tool
from Interface.sanbox import SandboxExecutor
import typer

@function_tool
async def execute_shell(command: str, allowed_network: bool=False):
    """
    在Docker沙箱中执行shell命令
    Args:
        command: shell指令或代码
        allowed_network: 是否开启网络连接（默认为False）
    Returns:
        结构化字典
    """
    typer.echo(typer.style(f"[执行中]正在执行shell命令：{command[:20]}",fg=typer.colors.WHITE))
    try:
        executor = SandboxExecutor(
            timeout=10,
            memory_limit="128m",
            network_access=allowed_network,
            allow_install=True
        )

        result = executor.run(command, lang="shell")
        return result
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

