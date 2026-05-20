import typer
from agents import function_tool
from typing import Literal, List

from src.Interfaces.Exception.SecurityException import SecurityException
from src.Interfaces.Resolver.SafePathResolver import resolve_safe_path
from src.Modules.CodeModules.CodeAgentRunner import code_agent_tool
from src.Modules.WebModules.WebAgentRunner import web_agent_tool
from src.Modules.FileModules.FileAgentRunner import file_agent_tool
import json

@function_tool
async def dispatcher(command: str, type: Literal["File", "Code", "Web"], only_path: str = "None")->str:
    """
    路由分配工具，接收一个字符串形式自然语言描述的指令和字符串类型的操作类型（仅限定于"File", "Code", "Web"）
    Args:
        command: 字符串类型，用自然语言描述，表示最小可执行步骤的指令，必须明确清晰指明具体任务
        type: 字符串类型，表示对应的操作类型
        only_path: 字符串类型，如果type为"Code"则表示要执行的文件路径（可以是文件或目录，如果是目录则要在command中指明要执行目录中的哪些代码文件），用于给Code操作初始化沙箱提供**唯一的**文件挂载点，如果操作涉及执行具体的代码文件/目录则**必须显式正确填写（不然Code操作无法进行）**，非"Code"操作禁止填写，"Code"操作不涉及具体代码文件/目录则不需要填写，默认值为"None"
    Returns:
        json字符串，结构如下：
        {
            "success": bool类型，表示该指令的操作是否成功，成功为True，失败为False,
            "tool_id": str类型，表示是哪种类型的工具完成了本次指令,
            "summary": str类型，操作概要,
            "data": 操作相关数据
            "need_confirmed": bool类型，是否需要用户确认，需要用户确认为True,否则为False
        }
    """
    typer.echo(typer.style(f"\n[Enter]路由：{type}，命令:{command}，路径参数：{only_path}", fg=typer.colors.WHITE))
    if (type == "File" or type == "Web") and only_path != "None":
        return json.dumps({
            "success": False,
            "tool_id": None,
            "summary": "只有'Code'操作才可以填写only_path参数",
            "data": None,
            "need_confirmed": False,
        }, ensure_ascii=False, indent=2)
    if only_path != "None":
        try:
            only_path = resolve_safe_path(only_path, "real")
        except SecurityException as e:
            return json.dumps({
                "success": False,
                "tool_id": None,
                "summary": f"文件路径不存在或不合法：{str(e)}，已拦截该指令",
                "data": None,
                "need_confirmed": False,
            }, ensure_ascii=False, indent=2)
    if type == "File":
        result = await file_agent_tool(command)
    elif type == "Code":
        result = await code_agent_tool(command, only_path)
    elif type == "Web":
        result = await web_agent_tool(command)
    else:
        return json.dumps({
            "success": False,
            "tool_id": None,
            "summary": "操作类型必须是File，Code，Web的其中一个",
            "data": None,
            "need_confirmed": False,
        }, ensure_ascii=False, indent=2)
    return result
