from dataclasses import dataclass, field
import typer
import json
from src.tools.tools_registry import get_tools_registry

PLAN_REMINDER_INTERVAL = 2  # 每隔2轮提醒一次

@dataclass
class PlanItem:
    content: str
    status: str = "pending"

@dataclass
class PlanningState:
    items: list[PlanItem] = field(default_factory=list)
    rounds_since_update: int = 0

class TodoManager:
    def __init__(self):
        self.state = PlanningState()

    #让类的可以像函数一样被调用
    def __call__(self, items: list):
        return self.update(items)

    #被LLM调用的工具，通过__call__调用
    def update(self, items: list) -> str:
        #BrainAgent列出的计划不能超过10条
        if len(items) > 10:
            return json.dumps({
                "success":"False",
                "error": "Too many items. Maximum allowed is 10."
            }, ensure_ascii=False)

        normalized = []
        in_progress_count = 0
        for index, item in enumerate(items):
            content = str(item.get("content", "")).strip()
            status = str(item.get("status", "pending")).lower()

            #content字段必须存在
            if not content:
                return json.dumps({
                    "success": "False",
                    "error": f"Item index:{index}: 此处的content参数不能为空"
                }, ensure_ascii=False)

            if status not in ["pending", "in_progress", "completed"]:
                return json.dumps({
                    "success": "False",
                    "error": f"Item index:{index}: status参数必须是'pending', 'in_progress'或'completed'"
                }, ensure_ascii=False)

            if status == "in_progress":
                in_progress_count += 1

            normalized.append(PlanItem(
                content = content,
                status = status
            ))

        if in_progress_count > 1:
                return json.dumps({
                    "success": "False",
                    "error": "Only one plan item can be in_progress"
                }, ensure_ascii=False)

        self.state.items = normalized
        self.state.rounds_since_update = 0
        return json.dumps({
            "success": "True",
            "summary": f"任务计划已成功更新: {normalized}"
        })

    def reminder(self) -> str | None:
        if not self.state.items:
            return None
        if self.state.rounds_since_update < PLAN_REMINDER_INTERVAL:
            return None
        return "<SYSTEM_REMINDER>在继续之前使用todo更新任务状态表</SYSTEM_REMINDER>"

    #可视化，只是给用户看的
    def render(self) -> None:
        if not self.state.items:
            return None

        typer.echo()
        typer.echo(typer.style(f"<任务计划>：", fg=typer.colors.YELLOW, bold=True))
        for item in self.state.items:
            marker = {
                "pending": "[ ]",
                "in_progress": "[>]",
                "completed": "[✓]"
            }.get(item.status)
            typer.echo(typer.style(f"{marker} {item.content}", fg=typer.colors.GREEN if item.status == "completed" else typer.colors.BRIGHT_CYAN if item.status == "in_progress" else typer.colors.WHITE))

        completed = sum(1 for item in self.state.items if item.status == "completed")
        typer.echo(typer.style(f"任务进度：{completed}/{len(self.state.items)}", fg=typer.colors.YELLOW))
        typer.echo()
        return None

TODO_SCHEMA = {
    "type": "function",
    "function": {
        "name": "todo",
        "description": "Rewrite the current session plan for multi-step work.",
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string"
                            },
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed"]
                            }
                        },
                        "required": ["content", "status"]
                    }
                }
            },
            "required": ["items"]
        }
    }
}

_TODO = TodoManager()

def todo():
    return _TODO

#注册工具
get_tools_registry().register_tool("todo", _TODO, TODO_SCHEMA, for_agent="Brain_Agent")


