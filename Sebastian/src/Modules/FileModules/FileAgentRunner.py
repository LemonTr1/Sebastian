from src.Interfaces.Capabilities.BrainCapabilities.CapabilityGuard import CapabilityGuard
from src.Interfaces.Capabilities.BrainCapabilities.InferCapabilities import infer_capabilities
from src.Agents.Sub_Agents.FileAgent import file_agent
from src.Interfaces.Exception.SecurityException import SecurityException
import typer
import json

async def file_agent_tool(command: str)->str:
    try:
        required_caps = await infer_capabilities(command)
        return await CapabilityGuard.run(file_agent, "File_Agent", command, required_caps, 20)
    except SecurityException as e:
        typer.echo(typer.style(f"安全警告：{e}", fg=typer.colors.RED))
        return json.dumps(
            {
                "success": False,
                "tool_id": "File",
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
                "tool_id": "File",
                "summary": f"权限错误：{e}",
                "data": None,
                "need_confirmed": False
            }, ensure_ascii=False, indent=2
        )
    except Exception as e:
        typer.echo(typer.style(f"Ops！File Agent 出现故障了：{e}", fg=typer.colors.RED))
        return json.dumps(
            {
                "success": False,
                "tool_id": "File",
                "summary": f"Ops！File Agent 出现故障了：{e}",
                "data": None,
                "need_confirmed": False
            }, ensure_ascii=False, indent=2
        )