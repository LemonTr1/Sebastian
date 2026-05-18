from agents import function_tool
from typing import Literal
from src.Agents.Sub_Agents.Code_Agent import code_agent_tool
from src.Agents.Sub_Agents.Web_agent import web_agent_tool
from src.Agents.Sub_Agents.File_agent import file_agent_tool
import json

@function_tool
async def dispatcher(command: str, type: Literal["File", "Code", "Web"])->str:
    """
    路由分配工具，接收一个字符串形式自然语言描述的指令和字符串类型的操作类型（仅限定于"File", "Code", "Web"）
    Args:
        command: 字符串类型，用自然语言描述，表示最小可执行步骤的指令，必须明确清晰指明具体任务
        type: 字符串类型，表示对应的操作类型
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
    if type == "File":
        result = await file_agent_tool(command)
    elif type == "Code":
        result = await code_agent_tool(command)
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
