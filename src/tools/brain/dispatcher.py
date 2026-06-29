import json
from src.tools.tools_registry import get_tools_registry

def dispatcher(task: str, type: str) -> str:
    from src.agents.file_agent import file_agent
    from src.agents.web_agent import web_agent
    from src.agents.memory_agent import memory_agent

    try:
        if type == "File":
            result = file_agent.run(task)
        elif type == "Web":
            result = web_agent.run(task)
        elif type == "Memory":
            result = memory_agent.run(task)
        else:
            return json.dumps(
                {
                    "success": False,
                    "tool_id": None,
                    "summary": "type必须为File/Web/Memory",
                    "data": None,
                    "need_confirmed": False
                },
                ensure_ascii=False
            )
    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "tool_id": type,
                "summary": f"{type} Agent 异常: {e}",
                "data": None,
                "need_confirmed": False
            },
            ensure_ascii=False
        )

    return result


DISPATCHER_SCHEMA = {
    "type": "function",
    "function": {
        "name": "dispatcher",
        "description": (
            "将任务分发到对应的子Agent执行。\n"
            "文件读写/文档→File，搜索/下载/时间/浏览器/网页→Web，知识库→Memory。\n"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "自然语言任务描述。用Markdown代码块包裹代码/Shell命令/文本内容。",
                },
                "type": {
                    "type": "string",
                    "enum": ["File", "Web", "Memory"],
                    "description": "目标Agent类型。File=文件读写/文档；Web=搜索/下载/浏览器/时间；Memory=知识库。",
                },
            },
            "required": ["command", "type"],
        },
    },
}

#注册工具
get_tools_registry().register_tool("dispatcher", dispatcher, DISPATCHER_SCHEMA, for_agent="Brain_Agent")
