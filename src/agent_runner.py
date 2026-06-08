import json
import typer
from src.config import get_client, MODEL
from src.tools.brain.todo_manager import todo

#以下为response.choice[0].message对象结构
#LLM的没有工具调用的回应格式：
'''
{
    "role": "assistant",
    "content": "你好，有什么可以帮你的？"
}
'''

#LLM存在工具调用的回应格式：
'''
{
  "role": "assistant",
  "content": "我来帮你查一下",
  "tool_calls": [
    {
      "id": "call_00_aBcDeFg1234567890",
      "type": "function",
      "function": {
        "name": "dispatcher",
        "arguments": "{\"command\": \"列出家目录\", \"type\": \"File\", \"only_path\": \"\"}"
      }
    }, 
    ...
  ]
}
'''

class AgentRunner:
    def __init__(
        self,
        name: str,
        instructions: str,
        tool_map: dict = None,
        hitl_tools: set = None,
        model: str = None,
    ):
        self.name = name
        self.instructions = instructions
        self.tool_map = tool_map or {}
        self.hitl_tools = hitl_tools or set()
        self.model = model or MODEL
        self.client = get_client()
        self.context = []

    def _ensure_system_prompt(self):
        if not self.context or self.context[0].get("role") != "system":
            self.context.insert(0, {"role": "system", "content": self.instructions})

    def _extract_assistant_msg(self, response) -> dict:
        """从 LLM 返回的原始响应里提取 assistant 消息"""
        msg = response.choices[0].message

        result = {"role": "assistant"}

        if msg.content:
            result["content"] = msg.content

        tool_calls = msg.tool_calls
        #如果存在工具调用
        if tool_calls:
            cleaned_calls = []
            for tc in tool_calls:
                cleaned_calls.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                })
            result["tool_calls"] = cleaned_calls

        return result

    #执行工具函数
    def _process_tool_calls(self, tool_calls: list) -> bool:
        aborted = False
        used_todo = False
        for tc in tool_calls:
            #OpenAI API契约规定：tool_calls数组有多少项，后面就必须用同样的role: tool消息回应，就是必须要告诉LLM结果是什么
            if aborted:
                err = json.dumps(
                    {"error": "由于前面的工具调用失败，此调用已被跳过（保证时序性）"},
                    ensure_ascii=False,
                )
                self.context.append({"role": "tool", "tool_call_id": tc["id"], "content": err})
                continue

            name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                err = json.dumps(
                    {
                        "error": f"工具 '{name}' 参数JSON格式解析发生错误，执行失败"
                    }, ensure_ascii=False
                )
                self.context.append({"role": "tool", "tool_call_id": tc["id"], "content": err})
                aborted = True
                continue

            if name not in self.tool_map:
                err = json.dumps(
                    {"error": f"工具 '{name}' 不存在，可用: {list(self.tool_map.keys())}"},
                    ensure_ascii=False,
                )
                self.context.append({"role": "tool", "tool_call_id": tc["id"], "content": err})
                aborted = True
                continue

            if name in self.hitl_tools:
                if not self._hitl_confirm(name, args):
                    err = json.dumps(
                        {"error": f"用户拒绝了工具 '{name}' 的执行。"},
                        ensure_ascii=False,
                    )
                    self.context.append({"role": "tool", "tool_call_id": tc["id"], "content": err})
                    aborted = True
                    continue

            tool_args = {k: v for k, v in args.items()}
            func = self.tool_map[name]["func"]
            try:
                typer.echo(typer.style(
                    f"\n> [TOOL] {self.name} 调用 {name}({_brief_args(tool_args)})",
                    fg=typer.colors.WHITE,
                ))
                #执行工具
                raw = func(**tool_args)
                result = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
                #标记本次AgentLoop中BrainAgent调用了任务管理工具
                if name == "todo":
                    used_todo = True
            except Exception as e:
                result = json.dumps(
                    {"error": f"工具 '{name}' 异常: {str(e)}"},
                    ensure_ascii=False,
                )
                aborted = True
            self.context.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
        return used_todo

    def run(self, task: str, max_turns: int = 50) -> str:
        self._ensure_system_prompt()
        self.context.append({"role": "user", "content": task})

        tool_schemas = (
            [v["schema"] for v in self.tool_map.values()]
            if self.tool_map
            else None
        )

        turn = 0
        while True:
            turn += 1
            if turn > max_turns:
                return "已达到最大对话轮次，请精简问题后重试"

            kwargs = dict(model=self.model, messages=self.context)
            if tool_schemas:
                kwargs["tools"] = tool_schemas
                kwargs["tool_choice"] = "auto"

            response = self.client.chat.completions.create(**kwargs)
            assistant_msg = self._extract_assistant_msg(response)
            self.context.append(assistant_msg)

            tool_calls = assistant_msg.get("tool_calls") or []
            if not tool_calls:
                return assistant_msg.get("content") or ""

            self._process_tool_calls(tool_calls)

    def run_stream(self, task: str, on_token=None, max_turns: int = 50) -> str:
        self._ensure_system_prompt()
        self.context.append({"role": "user", "content": task})

        tool_schemas = (
            [v["schema"] for v in self.tool_map.values()]
            if self.tool_map
            else None
        )

        turn = 0
        while True:
            turn += 1
            if turn > max_turns:
                return "已达到最大对话轮次，请精简问题后重试"
            kwargs = dict(model=self.model, messages=self.context)
            if tool_schemas:
                kwargs["tools"] = tool_schemas
                kwargs["tool_choice"] = "auto"

            stream = self.client.chat.completions.create(**kwargs, stream=True)

            collected_content = ""
            collected_tool_calls: dict[int, dict] = {}
            has_tool_calls = False

            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.tool_calls:
                    has_tool_calls = True
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in collected_tool_calls:
                            collected_tool_calls[idx] = {
                                "id": "",
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            }
                        buf = collected_tool_calls[idx]
                        if tc.id:
                            buf["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                buf["function"]["name"] += tc.function.name
                            if tc.function.arguments:
                                buf["function"]["arguments"] += tc.function.arguments
                if delta.content:
                    token = delta.content
                    collected_content += token
                    if not has_tool_calls and on_token:
                        on_token(token)

            tool_calls_list = [
                collected_tool_calls[i] for i in sorted(collected_tool_calls.keys())
            ]

            assistant_msg = {"role": "assistant", "content": collected_content or None}
            if tool_calls_list:
                assistant_msg["tool_calls"] = tool_calls_list
            assistant_msg = {k: v for k, v in assistant_msg.items() if v is not None}
            for tc in assistant_msg.get("tool_calls") or []:
                tc.pop("index", None)
            self.context.append(assistant_msg)

            if not tool_calls_list:
                return collected_content

            used_todo = self._process_tool_calls(tool_calls_list)
            if used_todo:
                #打印在终端给用户看
                todo().render()
            else:
                todo().state.rounds_since_update += 1
                reminder = todo().reminder()
                if reminder:
                    #插入一条系统提示
                    self.context.append({"role": "system", "content": reminder})


    #human-in-the-loop确认机制
    def _hitl_confirm(self, name: str, args: dict) -> bool:
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

    #初始化Agent,返回AgentRunner对象（代替构造函数）
    @classmethod
    def create_runner(cls, name: str, instructions: str, tools: list, hitl_tools: set = None, model: str = None, summary_hint: str = None):
        tool_map = {}
        for tool_func, schema in tools:
            tool_name = schema["function"]["name"]
            tool_map[tool_name] = {"func": tool_func, "schema": schema}
        return cls(
            name=name,
            instructions=instructions,
            tool_map=tool_map,
            hitl_tools=hitl_tools or set(),
            model=model,
        )

#将工具函数的参数从dict类型转化为更方便人类阅读的dict类型
def _brief_args(args: dict) -> str:
    parts = []
    for k, v in args.items():
        s = str(v)
        if len(s) > 80:
            s = s[:80] + "..."
        parts.append(f"{k}={s}")
    return ", ".join(parts)
