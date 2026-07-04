from src.hooks.hooks_registry import get_hooks_registry
from src.tools.tools_registry import get_tools_registry
import typer
import json

#human-in-the-loop确认机制
def _hitl_confirm(name: str, args: dict) -> bool:
    brief = {k: v for k, v in args.items()}
    typer.echo("")
    typer.echo(
        typer.style(
            "=" * 60,
            fg=typer.colors.YELLOW,
        )
    )
    typer.echo(
        typer.style(
            f"  [Warn] LLM 请求执行危险操作: {name}",
            fg=typer.colors.YELLOW,
            bold=True,
        )
    )
    for k, v in brief.items():
        val_str = str(v)
        if len(val_str) > 200:
            val_str = val_str[:200] + "..."
        typer.echo(typer.style(f"    {k}: {val_str}", fg=typer.colors.YELLOW))
    typer.echo(
        typer.style(
            "=" * 60,
            fg=typer.colors.YELLOW,
        )
    )
    return typer.confirm(typer.style("是否允许执行？", fg=typer.colors.YELLOW))

def hitl_hook(agent_name: str, tool_call: dict):
    """Human in the Loop钩子（三个功能：1.判断工具是否存在 2.tool_call中的参数格式是否正确 3.用户是否同意执行）"""
    tools, _ = get_tools_registry().get_tools_for_agent(agent_name)
    tool_name = tool_call["function"]["name"]
    #获取该Agent所有可用的工具名(str)，判断Agent即将调用的工具是否存在
    existed_tools_list = []
    for _, schema in tools:
        existed_tools_list.append(schema["function"]["name"])

    if tool_name not in existed_tools_list:
        return json.dumps({"error": f"There is no tool named: {tool_name}"}, ensure_ascii=False)

    #判断参数格式是否正确
    try:
        args = json.loads(tool_call["function"]["arguments"])
    except json.decoder.JSONDecodeError:
        return json.dumps({"error": f"工具 '{tool_name}' 参数JSON格式解析发生错误，执行失败"}, ensure_ascii=False)

    if get_tools_registry().is_hitl_tool(tool_name):
        if not _hitl_confirm(tool_name, args):
            return json.dumps(
                {"error": f"用户拒绝了工具 '{tool_name}' 的执行，询问用户并在得到用户的允许前不允许再次执行该工具。"},
                ensure_ascii=False,
            )

    return None

get_hooks_registry().register_hook("PreToolUse", hitl_hook)
