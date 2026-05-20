from src.Agents.Sub_Agents.CodeAgent import code_agent
from src.Interfaces.Capabilities.BrainCapabilities.CapabilityGuard import CapabilityGuard
from src.Interfaces.Capabilities.BrainCapabilities.InferCapabilities import infer_capabilities
from src.Interfaces.Exception.ImageNotFoundException import ImageNotFoundException
from src.Interfaces.Exception.SecurityException import SecurityException
import typer
import json

async def code_agent_tool(command: str, path: str)->str:
    try:
        required_caps = await infer_capabilities(command)
        return await CapabilityGuard.run(code_agent, "Code_Agent", command, required_caps, 20, path)
    except ImageNotFoundException as e:
        typer.echo(typer.style(f"请检查本地Docker服务，发生错误：{str(e)}", fg=typer.colors.RED))
        return json.dumps({
            "success": False,
            "tool_id": "Code",
            "summary": f"Code操作环境启动失败：{str(e)}",
            "data": None,
            "need_confirmed": False
        },ensure_ascii=False, indent=2)
    except SecurityException as e:
        typer.echo(typer.style(f"安全警告：{e}", fg=typer.colors.RED))
        return json.dumps(
            {
                "success": False,
                "tool_id": "Code",
                "summary": f"安全警告：{e}",
                "data": None,
                "need_confirmed": False
            }, ensure_ascii=False, indent=2
        )
    except PermissionError as e:
        typer.echo(typer.style(f"权限错误：{e}", fg=typer.colors.RED))
        return json.dumps(
            {
                "success": False,
                "tool_id": "Code",
                "summary": f"权限错误：{e}",
                "data": None,
                "need_confirmed": False
            }, ensure_ascii=False, indent=2
        )
    except Exception as e:
        typer.echo(typer.style(f"Ops！Code Agent 出现故障了：{e}", fg=typer.colors.RED))
        return json.dumps(
            {
                "success": False,
                "tool_id": "Code",
                "summary": f"Ops！Code Agent 出现故障了：{e}",
                "data": None,
                "need_confirmed": False
            }, ensure_ascii=False, indent=2
        )