from src.Agents.Sub_Agents.WebAgent import web_agent
from src.Interfaces.Capabilities.BrainCapabilities.CapabilityGuard import CapabilityGuard
from src.Interfaces.Capabilities.BrainCapabilities.InferCapabilities import infer_capabilities
from src.Interfaces.Exception.SecurityException import SecurityException
import typer
import json

async def web_agent_tool(command: str)->str:
    try:
        required_caps = await infer_capabilities(command)
        return await CapabilityGuard.run(web_agent, "Web_Agent", command, required_caps, 20)
    except SecurityException as e:
        typer.echo(typer.style(f"安全警告：{e}", fg=typer.colors.RED))
        return json.dumps(
            {
                "success": False,
                "tool_id": "Web",
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
                "tool_id": "Web",
                "summary": f"权限错误：{e}",
                "data": None,
                "need_confirmed": False
            }, ensure_ascii=False, indent=2
        )
    except Exception as e:
        typer.echo(typer.style(f"Ops！Web Agent 出现故障了：{e}", fg=typer.colors.RED))
        return json.dumps(
            {
                "success": False,
                "tool_id": "Web",
                "summary": f"Ops！Web Agent 出现故障了：{e}",
                "data": None,
                "need_confirmed": False
            }, ensure_ascii=False, indent=2
        )