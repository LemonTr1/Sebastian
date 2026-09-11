from src.hooks.hooks_registry import get_hooks_registry
from src.tools.tools_registry import get_tools_registry
from src.utils.approval_client import ApprovalClient
from src.utils.eval_flag import is_eval_mode
from src.utils.memory_system import MEMORY_SYSTEM
from src.logs.app_log import get_log
import typer
import json

_approval_client = ApprovalClient(theme="dark")

def hitl_hook(agent_name: str, tool_call: dict):
    """Human in the Loop钩子（三个功能：1.判断工具是否存在 2.tool_call中的参数格式是否正确 3.弹窗确认用户是否同意执行）"""
    tools, _ = get_tools_registry().get_tools_for_agent(agent_name)
    tool_name = tool_call["function"]["name"]
    existed_tools_list = []
    for _, schema in tools:
        existed_tools_list.append(schema["function"]["name"])

    if tool_name not in existed_tools_list:
        return json.dumps({"error": f"There is no tool named: {tool_name}"}, ensure_ascii=False)

    try:
        args = json.loads(tool_call["function"]["arguments"])
    except json.decoder.JSONDecodeError:
        return json.dumps({"error": f"工具 '{tool_name}' 参数JSON格式解析发生错误，执行失败"}, ensure_ascii=False)

    if get_tools_registry().is_hitl_tool(tool_name):
        #-------------Eval测试部分（Eval环境下会屏蔽HITL钩子）---------------
        if is_eval_mode():
            get_log().info(f"[EVAL] auto-approve {tool_name}")
            typer.echo(typer.style(
                f"\n> [EVAL] 自动批准: {tool_name}",
                fg=typer.colors.CYAN,
            ))
            return None

        if tool_name in ("write", "edit") and MEMORY_SYSTEM.is_memory_path(args.get("file_path")):
            get_log().info(f"[memory] skip HITL for {tool_name} {args.get('file_path')}")
            return None

        #---------------------------------------
        typer.echo(typer.style(
            f"\n> [HITL] 弹窗等待用户审批: {tool_name} ...",
            fg=typer.colors.YELLOW, bold=True,
        ))
        if not _approval_client.ask(tool_name, args):
            return json.dumps(
                {"error": f"用户拒绝了工具 '{tool_name}' 的执行，询问用户并在得到用户的允许前不允许再次执行该工具。"},
                ensure_ascii=False,
            )

    return None

get_hooks_registry().register_hook("PreToolUse", hitl_hook)
