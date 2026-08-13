import json
import random
import time
import threading
import typer
from src.config import get_client, MODEL
from src.hooks.hooks_registry import get_hooks_registry
from src.tools.toolkits.todo_manager import todo
from src.tools.tools_registry import ToolsRegistry
from src.logs.app_log import get_log
from src.utils.compaction_pipeline import CompactionPipeline, reactive_compact
from src.utils.memory_system import MEMORY_SYSTEM
from src.utils.exceptions import CompactException, SubAgentRuntimeException

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

#回应工具调用请求格式：
'''
{
    "role": "tool", 
    "tool_call_id": <工具id>, 
    "content": <工具调用结果>
}
'''

logger = get_log()

class AgentRunner:
    def __init__(
        self,
        name: str,
        instructions: str,
        registry: ToolsRegistry,
        model: str = None,
    ):
        self.name = name
        self.instructions = instructions
        tools, _ = registry.get_tools_for_agent(name)
        tool_map = {}
        for func, schema in tools:
            tool_map[schema["function"]["name"]] = {"func": func, "schema": schema}
        self.tool_map = tool_map
        self.model = model or MODEL
        self.client = get_client()
        self.context = []
        self._bg_counter = 0
        self.background_tasks: dict[str, dict] = {}
        self.background_results: dict[str, str] = {}
        self.background_lock = threading.Lock()
        #hitl审批需要加锁
        self.pre_tool_use_lock = threading.Lock()
        #统计本轮tokens消耗需要加锁
        self.post_completion_lock = threading.Lock()

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

    def should_run_background(self, tool_args: dict) -> bool:
        """判断是否应该在后台运行工具"""
        if tool_args.get("run_in_background"):
            return True

        return False

    def start_background_task(self, tool_call_id: str, tool_name: str, tool_args: dict) -> str:
        self._bg_counter += 1
        bg_id = f"bg_task_{self._bg_counter}"
        cmd = f"{tool_name}: {json.dumps(tool_args, ensure_ascii=False)}"

        def worker():
            func = self.tool_map[tool_name]["func"]
            result = func(**tool_args)
            with self.background_lock:
                self.background_tasks[bg_id]["status"] = "completed"
                self.background_results[bg_id] = result

        with self.background_lock:
            self.background_tasks[bg_id] = {
                "tool_call_id": tool_call_id,
                "command": cmd,
                "status": "running",
            }

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        typer.echo(typer.style(f"\n> [background] 后台任务启动：{bg_id}: {cmd[:40]} ... ", fg=typer.colors.WHITE, bold=True))
        return bg_id

    def collect_background_results(self) -> list:
        with self.background_lock:
            ready_ids = [bid for bid, task in self.background_tasks.items() if task["status"] == "completed"]

        notifications = []
        for bg_id in ready_ids:
            with self.background_lock:
                task = self.background_tasks.pop(bg_id)
                output = self.background_results.pop(bg_id, "")
            notifications.append(
                f"<task_notification>\n"
                f"  <task_id>{bg_id}</task_id>\n"
                f"  <status>completed</status>\n"
                f"  <command>{task['command']}</command>\n"
                f"  <output>{output}</output>\n"
                f"</task_notification>"
            )
            typer.echo(typer.style(f"\n> [background done] {bg_id}: {task['command']} ...", fg=typer.colors.GREEN))
        return notifications

    #执行工具函数
    def _process_tool_calls(self, tool_calls: list) -> bool:
        aborted = False
        used_todo = False

        new_messages = []
        for tc in tool_calls:
            #OpenAI API契约规定：tool_calls数组有多少项，后面就必须用同样的role: tool消息回应，就是必须要告诉LLM结果是什么
            if aborted:
                err = json.dumps(
                    {"error": "由于前面的工具调用失败，此调用已被跳过（保证时序性）"},
                    ensure_ascii=False,
                )
                self.context.append({"role": "tool", "tool_call_id": tc["id"], "content": err})
                continue

            #在此插入PreToolUse钩子
            with self.pre_tool_use_lock:
                hook_result = get_hooks_registry().trigger_hooks("PreToolUse", self.name, tc)
                if hook_result is not None:
                    aborted = True
                    self.context.append({"role": "tool", "tool_call_id": tc["id"], "content": hook_result})
                    continue

            try:
                name = tc["function"]["name"]
                args = json.loads(tc["function"]["arguments"])
                tool_args = {k: v for k, v in args.items()}
                func = self.tool_map[name]["func"]
                typer.echo(typer.style(
                    f"\n> [TOOL] {self.name} 调用 {name}({_brief_args(tool_args)})",
                    fg=typer.colors.WHITE,
                ))

                #执行工具
                if self.should_run_background(args):
                    bg_id = self.start_background_task(tc["id"], name, tool_args)
                    new_messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": f"<SYSTEM_REMINDER>Background task {bg_id} started, result will be available when complete.</SYSTEN_REMINDER>"
                    })
                else:
                    raw = func(**tool_args)
                    result = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
                    new_messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result
                    })

                #标记本次AgentLoop中BrainAgent调用了任务管理工具
                if name == "todo":
                    used_todo = True
                    if self.context[0]["role"] == "system":
                        self.context[0]["context"] = self.context[0].get("context", "") + "\n\n" + "<当前任务计划>" + "\n" + todo().get_normalized()

            except Exception as e:
                tool_name = tc.get("function", {}).get("name", "unknown")
                result = json.dumps(
                    {"error": f"工具 '{tool_name}' 异常: {str(e)}"},
                    ensure_ascii=False,
                )
                aborted = True

        # 注入后台任务运行结果
        bg_notifications = self.collect_background_results()
        if bg_notifications:
            new_messages.append({"role": "user", "content": ".\n".join(bg_notifications)})

        self.context.extend(new_messages)
        return used_todo

    #给子Agent用的（退出AgentLoop即清空上下文）
    def run(self, task: str, max_turns: int = 50) -> str:
        self._ensure_system_prompt()
        question = {"role": "user", "content": task}

        tool_schemas = (
            [v["schema"] for v in self.tool_map.values()]
            if self.tool_map
            else None
        )

        turn = 0
        #AgentLoop
        while True:
            turn += 1
            if turn > max_turns:
                self.context = []
                raise SubAgentRuntimeException("<SYSTEM_REMINDER>已达到最大对话轮次，请精简问题后重试</SYSTEM_REMINDER>")

            try:
                self.context = CompactionPipeline.compact(self.context)
            except CompactException as e:
                raise SubAgentRuntimeException(f"\n [ERROR]{e} \n ")

            kwargs = dict(model=self.model, messages=self.context + [question])
            if tool_schemas:
                kwargs["tools"] = tool_schemas
                kwargs["tool_choice"] = "auto"

            response = None
            retries = 0
            while True:
                if retries >= 5:
                    break
                try:
                    response = self.client.chat.completions.create(**kwargs)
                    break
                except Exception as e:
                    #如果是上下文溢出导致的异常
                    if "prompt_too_long" in str(e).lower() or "too many tokens" in str(e).lower() or "context_length_exceeded" in str(e).lower():
                        reactive_retries = 0
                        while True:
                            if reactive_retries >= 3:
                                break
                            logger.warning(f"{self.name}上下文过长，启动应急压缩，重试次数：{reactive_retries}")
                            try:
                                self.context = reactive_compact(self.context)
                                break
                            except CompactException:
                                reactive_retries += 1
                                continue
                    #如果是其他错误如API响应失败
                    else:
                        logger.error(f"{self.name}发生错误：{str(e)}")
                        delay = min(3, 2 ** retries)
                        time.sleep(random.uniform(0, delay))
                    retries += 1

            if response is None:
                self.context = []
                raise SubAgentRuntimeException(f"<SYSTEM_REMINDER>{self.name}出错无法恢复，请重试</SYSTEM_REMINDER>")

            with self.post_completion_lock:
                result = get_hooks_registry().trigger_hooks("PostCompletion", response)
                if result is not None:
                    logger.error(f"PostCompletion钩子触发错误：{result}")
                    typer.echo(typer.style(result, fg=typer.colors.RED, bold=True))

            assistant_msg = self._extract_assistant_msg(response)
            self.context.append(assistant_msg)

            tool_calls = assistant_msg.get("tool_calls") or []
            if not tool_calls:
                self.context = []
                #返回子Agent最后一轮总结
                return assistant_msg.get("content") or ""

            self._process_tool_calls(tool_calls)

    #流式输出，给brain_agent用的
    def run_stream(self, task: str, on_token=None, max_turns: int = 50) -> None:
        self._ensure_system_prompt()
        memories_content = MEMORY_SYSTEM.load_memories(self.context)

        question = {"role": "user", "content": memories_content + "\n\n" if memories_content else "" + task}

        tool_schemas = (
            [v["schema"] for v in self.tool_map.values()]
            if self.tool_map
            else None
        )

        turn = 0
        #AgentLoop
        while True:
            turn += 1
            if turn > max_turns:
                typer.echo("已达到最大对话轮次，请精简问题后重试")
                return

            # 保存压缩前快照，用于准确提取记忆
            pre_compress = [
                m if isinstance(m, dict) else {"role": m.get("role", ""), "content": str(m.get("content", ""))}
                for m in self.context
            ]

            # 压缩管线
            try:
                self.context = CompactionPipeline.compact(self.context)
            except CompactException as e:
                logger.error(f"\n [ERROR]{e} \n ")
                typer.echo(typer.style(f"\n [ERROR]{e} \n ", fg=typer.colors.RED, bold=True))
                pass

            kwargs = dict(model=self.model, messages=self.context + [question])
            if tool_schemas:
                kwargs["tools"] = tool_schemas
                kwargs["tool_choice"] = "auto"

            stream = None
            retries = 0
            while True:
                if retries >= 5:
                    break
                try:
                    stream = self.client.chat.completions.create(**kwargs, stream=True,
                                                                 stream_options={"include_usage": True})
                    break
                except Exception as e:
                    # 如果是上下文溢出导致的异常
                    if "prompt_too_long" in str(e).lower() or "too many tokens" in str(
                            e).lower() or "context_length_exceeded" in str(e).lower():
                        reactive_retries = 0
                        while True:
                            if reactive_retries >= 3:
                                break
                            logger.warning(f"{self.name}上下文过长，启动应急压缩，重试次数：{reactive_retries}")
                            try:
                                self.context = reactive_compact(self.context)
                                break
                            except CompactException:
                                reactive_retries += 1
                                continue
                    # 如果是其他错误如API响应失败
                    else:
                        logger.error(f"{self.name}发生错误：{str(e)}")
                        delay = min(3, 2 ** retries)
                        time.sleep(random.uniform(0, delay))
                    retries += 1

            if stream is None:
                logger.error(f"{self.name}出错无法恢复，请稍后重试")
                typer.echo(typer.style(f"\n {self.name}出错无法恢复，请稍后重试 \n", fg=typer.colors.RED, bold=True))
                return

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

                #在每个chunk结束后触发PostCompletion钩子，主要用于统计Token消耗
                if chunk.usage:
                    with self.post_completion_lock:
                        result = get_hooks_registry().trigger_hooks("PostCompletion", chunk)
                        if result is not None:
                            logger.error(f"PostCompletion钩子触发错误：{result}")
                            typer.echo(typer.style(result, fg=typer.colors.RED, bold=True))

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
                MEMORY_SYSTEM.extract_memories(pre_compress)
                MEMORY_SYSTEM.consolidate_memories()
                return

            used_todo = self._process_tool_calls(tool_calls_list)
            if used_todo:
                #打印在终端给用户看
                todo().render()
            else:
                todo().state.rounds_since_update += 1
                reminder = todo().reminder()
                if reminder:
                    #插入一条系统提示
                    self.context.append({"role": "user", "content": reminder})

    #提供外界获取上下文的接口
    def get_context(self):
        return self.context

    #提供外界初始化上下文的接口
    def set_context(self, context: list):
        self.context = context

    #初始化Agent,返回AgentRunner对象（代替构造函数）
    @classmethod
    def create_runner(cls, name: str, instructions: str, registry: ToolsRegistry, model: str = None):
        return cls(name=name, instructions=instructions, registry=registry, model=model)

#将工具函数的参数从dict类型转化为更方便人类阅读的dict类型
def _brief_args(args: dict) -> str:
    parts = []
    for k, v in args.items():
        s = str(v)
        if len(s) > 80:
            s = s[:80] + "..."
        parts.append(f"{k}={s}")
    return ", ".join(parts)
