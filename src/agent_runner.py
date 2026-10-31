import json
import random
import time
import threading
from collections.abc import Callable
import typer
from src.config import get_client, MODEL, is_vision_model
from src.hooks.hooks_registry import get_hooks_registry
from src.tools.toolkits.todo_manager import todo
from src.tools.tools_registry import ToolsRegistry
from src.logs.app_log import get_log
from src.utils.compaction_pipeline import (
    CompactionPipeline,
    reactive_compact,
    persist_content,
    NOTIFICATION_CAP,
    PERSISTED_REGISTRY,
    build_persisted_placeholder,
)
from src.utils import ui_redraw
from src.utils.memory_system import MEMORY_SYSTEM
from src.utils.agent_mode import AGENT_MODE
from src.utils.exceptions import CompactException, SubAgentRuntimeException
from src.utils.wake_queue import BRAIN_OWNER, WAKE_QUEUE, WakeEvent

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

#轮次上限的收尾提示：最后一轮不再给工具，强制模型输出阶段性总结
FINAL_TURN_PROMPT = (
    "<SYSTEM_REMINDER>已达到本次任务的最大执行轮次。"
    "现在不要再调用任何工具，立即用简洁的文字收尾："
    "1. 已完成的工作与产物（列出改动或创建的文件路径）；"
    "2. 未完成的工作及原因；"
    "3. 给主 Agent 或用户的下一步建议。"
    "如果任务已经完成，直接给出最终结果。</SYSTEM_REMINDER>"
)

TURN_LIMIT_FALLBACK = "已达到最大对话轮次，任务可能未全部完成；模型未返回收尾总结。"

class AgentRunner:
    def __init__(
        self,
        name: str,
        instructions: str | Callable[[], str],
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
        self.background_lock = threading.Lock()
        #统一收件箱地址：Brain 固定，子 Agent 每实例唯一，避免并发同名子 Agent 互相取走事件
        self.inbox_id = BRAIN_OWNER if name == BRAIN_OWNER else f"{name}#{id(self)}"
        self._closed = False
        #hitl审批需要加锁
        self.pre_tool_use_lock = threading.Lock()
        #统计本轮tokens消耗需要加锁
        self.post_completion_lock = threading.Lock()

        #子 Agent 最后一轮回复，用于回传给 Brain
        self.last_reply = ""
        #本次运行是否因轮次上限被强制收尾
        self.hit_turn_limit = False

    def _resolve_instructions(self) -> str:
        if callable(self.instructions):
            return self.instructions()
        return self.instructions

    def _ensure_system_prompt(self):
        content = self._resolve_instructions()
        if self.name == "Brain_Agent":
            mem_section = MEMORY_SYSTEM.instruction_block()
            if mem_section:
                content = content + mem_section
            #Plan 模式：动态注入只读规划提示词
            if AGENT_MODE.is_plan():
                content = content.rstrip() + "\n\n" + AGENT_MODE.describe(self.tool_map.keys())
            #由于尽可能命中输入缓存，将todo状态表注入到上下文最末尾中
            # if todo().state.items:
               # content = content.rstrip() + "\n\n" + "<当前任务计划>\n" + todo().get_normalized() + "\n</当前任务计划>"
        #已落盘文件清单：Brain 与子 Agent 均注入，防止反复读取大文件
        reg_section = PERSISTED_REGISTRY.describe()
        if reg_section:
            content = content.rstrip() + "\n\n" + reg_section
        if not self.context or self.context[0].get("role") != "system":
            self.context.insert(0, {"role": "system", "content": content})
        else:
            self.context[0]["content"] = content

    def _update_system_plan(self):
        """把最新任务计划替换进 system 提示词（同轮内替换式，不累积，保留落盘清单）"""
        if not self.context or self.context[0].get("role") != "system":
            return
        content = self.context[0].get("content", "")
        start = content.find("<当前任务计划>")
        end = content.find("</当前任务计划>")
        new_block = "<当前任务计划>\n" + todo().get_normalized() + "\n</当前任务计划>"
        if start != -1 and end != -1:
            content = content[:start] + new_block + content[end + len("</当前任务计划>"):]
        else:
            content = content.rstrip() + "\n\n" + new_block
        self.context[0]["content"] = content

    def _extract_assistant_msg(self, response) -> dict:
        """从 LLM 返回的原始响应里提取 assistant 消息"""
        choices = getattr(response, "choices", None)
        if not choices:
            logger.warning("LLM 响应中没有 choices，返回空 assistant 消息")
            return {"role": "assistant", "content": None}
        msg = choices[0].message

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

    def _active_tool_map(self) -> dict:
        """当前模式下 Brain 的可用工具表（Plan 模式施加白名单）"""
        if self.name == "Brain_Agent" and AGENT_MODE.is_plan():
            allowed = AGENT_MODE.allowed_tools()
            return {k: v for k, v in self.tool_map.items() if k in allowed}
        return self.tool_map

    def should_run_background(self, name: str, tool_args: dict) -> bool:
        """判断是否应该在后台运行工具"""
        if not name.lower() in ["bash", "agent"]:
            return False

        if tool_args.get("run_in_background"):
            return True

        return False

    def start_background_task(self, tool_call_id: str, tool_name: str, tool_args: dict, tool_map: dict | None = None) -> str:
        self._bg_counter += 1
        bg_id = f"bg_task_{self._bg_counter}"
        cmd = f"{tool_name}: {json.dumps(tool_args, ensure_ascii=False)}"

        def worker():
            try:
                active_map = tool_map or self.tool_map
                func = active_map[tool_name]["func"]
                result = func(**tool_args)
            except Exception as e:
                result = json.dumps({
                    "success": False,
                    "error": f"后台任务：{bg_id}出现异常: {str(e)}"
                }, ensure_ascii=False)

            try:
                notification = self._format_background_notification(bg_id, cmd, result)
            except Exception as e:
                logger.error(f"后台任务 {bg_id} 结果格式化失败：{str(e)}")
                notification = (
                    f"<task_notification>\n"
                    f"  <task_id>{bg_id}</task_id>\n"
                    f"  <status>completed</status>\n"
                    f"  <command>{cmd}</command>\n"
                    f"  <output>结果格式化失败：{str(e)}</output>\n"
                    f"</task_notification>"
                )

            if self.name == BRAIN_OWNER:
                typer.echo(typer.style(f"\n> [background done] {bg_id}: {cmd} ...", fg=typer.colors.GREEN))
            with self.background_lock:
                self.background_tasks.pop(bg_id, None)
                #子 Agent 结束后没有人消费它的事件，直接丢弃；Brain 永不关闭
                if self._closed:
                    return
                WAKE_QUEUE.enqueue(WakeEvent(
                    owner=self.inbox_id,
                    kind="background",
                    content=notification,
                ))

        with self.background_lock:
            self.background_tasks[bg_id] = {
                "tool_call_id": tool_call_id,
                "command": cmd,
                "status": "running",
            }

        if self.name == BRAIN_OWNER:
            typer.echo(typer.style(f"\n> [background] 后台任务启动：{bg_id}: {cmd[:40]} ... ", fg=typer.colors.WHITE, bold=True))
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        return bg_id

    def _format_background_notification(self, bg_id: str, command: str, output: str) -> str:
        #后台输出超限时落盘，仅注入占位符（带防重读指引）
        if len(output) > NOTIFICATION_CAP:
            file_path, digest, hits = persist_content(output, source="background")
            output = build_persisted_placeholder(output, file_path, digest, hits)
        return (
            f"<task_notification>\n"
            f"  <task_id>{bg_id}</task_id>\n"
            f"  <status>completed</status>\n"
            f"  <command>{command}</command>\n"
            f"  <output>{output}</output>\n"
            f"</task_notification>"
        )

    def _inject_wake_events(self) -> int:
        """把收件箱中属于本 Agent 的事件注入上下文，返回注入条数"""
        events = WAKE_QUEUE.drain(self.inbox_id)
        for event in events:
            self.context.append({"role": "user", "content": event.content})
        return len(events)

    #执行工具函数
    def _process_tool_calls(self, tool_calls: list, tool_map: dict | None = None) -> bool:
        aborted = False
        used_todo = False
        active_map = tool_map if tool_map is not None else self.tool_map

        new_messages = []
        for tc in tool_calls:
            #OpenAI API契约规定：tool_calls数组有多少项，后面就必须用同样的role: tool消息回应，就是必须要告诉LLM结果是什么
            if aborted:
                err = json.dumps(
                    {"error": "由于前面的工具调用失败，此调用已被跳过（保证时序性）"},
                    ensure_ascii=False,
                )
                new_messages.append({"role": "tool", "tool_call_id": tc["id"], "content": err})
                continue

            name = tc.get("function", {}).get("name", "")
            #Plan 模式硬限制：白名单外的工具直接拒绝（先于钩子与执行）
            if name and name not in active_map:
                result = json.dumps(
                    {
                        "error": f"工具 '{name}' 在当前 Plan 模式下不可用。"
                        f"可用工具：{sorted(active_map.keys())}。"
                        f"请专注于规划，或引导用户输入 /build 退出 Plan 模式后再执行。"
                    },
                    ensure_ascii=False,
                )
                new_messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
                logger.warning(f"{self.name} 在 Plan 模式下尝试调用禁用工具：{name}")
                continue

            #在此插入PreToolUse钩子
            with self.pre_tool_use_lock:
                hook_result = get_hooks_registry().trigger_hooks("PreToolUse", self.name, tc)
                if hook_result is not None:
                    aborted = True
                    new_messages.append({"role": "tool", "tool_call_id": tc["id"], "content": hook_result})
                    continue

            try:
                args = json.loads(tc["function"]["arguments"])
                tool_args = {k: v for k, v in args.items()}
                func = active_map[name]["func"]
                #子 Agent 的工具调用不打印到终端，只在日志里留痕
                if self.name == "Brain_Agent":
                    typer.echo(typer.style(
                        f"\n> [TOOL] {self.name} 调用 {name}({_brief_args(tool_args)})",
                        fg=typer.colors.WHITE,
                    ))

                #执行工具
                if self.should_run_background(name, args):
                    bg_id = self.start_background_task(tc["id"], name, tool_args, active_map)
                    new_messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": f"<SYSTEM_REMINDER>Background task {bg_id} started, result will be available when complete.</SYSTEM_REMINDER>"
                    })
                else:
                    raw = func(**tool_args)
                    #多模态工具（如 read 读取图片）：content 直接使用 OpenAI content-parts 列表（含 image_url），
                    #让具备视觉能力的模型能接收到图片，而不是被 json.dumps 成字符串丢掉图像信息
                    if isinstance(raw, dict) and raw.get("__multimodal__"):
                        content_payload = raw.get("parts") or [{"type": "text", "text": ""}]
                        #优雅降级：当前模型不支持视觉时，剥离 image_url，仅保留文本提示，
                        #避免纯文本模型收到 image part 触发 OpenAI 兼容 API 400 报错导致 Agent 崩溃
                        if not is_vision_model(self.model):
                            content_payload = _downgrade_multimodal(content_payload)
                        new_messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": content_payload
                        })
                    else:
                        result = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
                        new_messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": result
                        })

                #标记本次AgentLoop中BrainAgent调用了任务管理工具
                if name == "todo":
                    used_todo = True
                    self._update_system_plan()

            except Exception as e:
                tool_name = tc.get("function", {}).get("name", "unknown")
                result = json.dumps(
                    {"error": f"工具 '{tool_name}' 异常: {str(e)}"},
                    ensure_ascii=False,
                )
                new_messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
                logger.error(f"工具 '{tool_name}' 异常: {str(e)}")
                aborted = True

        self.context.extend(new_messages)
        return used_todo

    #给子Agent用的（退出AgentLoop即清空上下文）
    def run(self, task: str, max_turns: int = 50) -> str:
        self._closed = False
        try:
            return self._run(task, max_turns)
        finally:
            #子 Agent 结束后清掉无人消费的事件；后台 worker 也会检查 _closed 不再投递
            if self.name != BRAIN_OWNER:
                with self.background_lock:
                    self._closed = True
                    WAKE_QUEUE.drop_owner(self.inbox_id)

    def _run(self, task: str, max_turns: int = 50) -> str:
        self.last_reply = ""
        self.hit_turn_limit = False
        self._ensure_system_prompt()
        self._inject_wake_events()
        self.context.append({"role": "user", "content": task})

        tool_schemas = (
            [v["schema"] for v in self.tool_map.values()]
            if self.tool_map
            else None
        )

        turn = 0
        #AgentLoop
        while True:
            turn += 1
            #运行中到达的 cron/后台事件在每轮开头注入
            self._inject_wake_events()
            #最后一轮保留给收尾总结：不给工具，强制模型输出文字
            final_turn = turn >= max_turns

            # 每轮评估压缩管线（按预算逐层触发）
            try:
                self.context = CompactionPipeline.compact(self.context)
            except CompactException as e:
                logger.error(f"\n [ERROR]{e} \n ")
                typer.echo(typer.style(f"\n [ERROR]{e} \n ", fg=typer.colors.RED, bold=True))
            #压缩后兜底恢复system提示词
            if self.context and self.context[0].get("role") != "system":
                self._ensure_system_prompt()

            if final_turn:
                self.hit_turn_limit = True
                self.context.append({"role": "user", "content": FINAL_TURN_PROMPT})

            kwargs = dict(model=self.model, messages=self.context)
            if tool_schemas and not final_turn:
                kwargs["tools"] = tool_schemas
                kwargs["tool_choice"] = "auto"

            # 必须先初始化：重试全部失败时下面依赖 response is None 抛出可读错误，否则会 UnboundLocalError
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
                                #关键：重试必须使用压缩后的上下文
                                kwargs["messages"] = self.context
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

            #收尾轮即使模型仍请求工具也不再执行，直接采用本轮文字作为总结
            tool_calls = [] if final_turn else (assistant_msg.get("tool_calls") or [])
            if not tool_calls:
                self.last_reply = assistant_msg.get("content") or ""
                if final_turn and not self.last_reply:
                    self.last_reply = TURN_LIMIT_FALLBACK
                self.context = []
                #返回子Agent最后一轮总结
                return self.last_reply

            self._process_tool_calls(tool_calls)

    #流式输出，给brain_agent用的
    def run_stream(self, task: str | None, on_token=None, max_turns: int = 50) -> None:
        self.last_reply = ""
        self.hit_turn_limit = False
        self._ensure_system_prompt()
        injected = self._inject_wake_events()
        if task is not None:
            self.context.append({"role": "user", "content": task})

        #无用户任务、无待处理事件：队列线程的空唤醒直接结束
        if task is None and injected == 0:
            return

        #Plan 模式对 Brain 施加工具白名单
        active_map = self._active_tool_map()
        tool_schemas = (
            [v["schema"] for v in active_map.values()]
            if active_map
            else None
        )

        turn = 0
        #AgentLoop
        while True:
            turn += 1
            #运行中到达的 cron/后台事件在每轮开头注入
            self._inject_wake_events()
            #最后一轮保留给收尾总结：不给工具，强制模型输出文字
            final_turn = turn >= max_turns

            # 每轮评估压缩管线（按预算逐层触发）
            try:
                self.context = CompactionPipeline.compact(self.context)
            except CompactException as e:
                logger.error(f"\n [ERROR]{e} \n ")
                typer.echo(typer.style(f"\n [ERROR]{e} \n ", fg=typer.colors.RED, bold=True))
            #压缩后兜底恢复system提示词
            if self.context and self.context[0].get("role") != "system":
                self._ensure_system_prompt()

            if final_turn:
                self.hit_turn_limit = True
                self.context.append({"role": "user", "content": FINAL_TURN_PROMPT})

            kwargs = dict(model=self.model, messages=self.context)
            if tool_schemas and not final_turn:
                kwargs["tools"] = tool_schemas
                kwargs["tool_choice"] = "auto"

            stream = None
            retries = 0
            use_stream_options = True
            while True:
                if retries >= 5:
                    break
                create_kwargs = dict(kwargs, stream=True)
                if use_stream_options:
                    create_kwargs["stream_options"] = {"include_usage": True}
                try:
                    stream = self.client.chat.completions.create(**create_kwargs)
                    break
                except Exception as e:
                    err = str(e).lower()
                    # 供应商不支持 stream_options/include_usage → 去掉该参数重试一次
                    if use_stream_options and ("stream_options" in err or "include_usage" in err):
                        logger.warning(f"{self.name} 供应商不支持 stream_options/include_usage，回退为普通流式调用")
                        use_stream_options = False
                        continue
                    # 如果是上下文溢出导致的异常
                    if "prompt_too_long" in err or "too many tokens" in err or "context_length_exceeded" in err:
                        reactive_retries = 0
                        while True:
                            if reactive_retries >= 3:
                                break
                            logger.warning(f"{self.name}上下文过长，启动应急压缩，重试次数：{reactive_retries}")
                            try:
                                self.context = reactive_compact(self.context)
                                #关键：重试必须使用压缩后的上下文
                                kwargs["messages"] = self.context
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
                return f"[ERROR] {self.name} 调用模型失败，已达到最大重试次数，请稍后重试。"

            collected_content = ""
            collected_tool_calls: dict[int, dict] = {}
            has_tool_calls = False

            for chunk in stream:
                # usage-only 终止块（choices 为空，仅携带 usage）——先处理，避免索引越界
                if getattr(chunk, "usage", None):
                    with self.post_completion_lock:
                        result = get_hooks_registry().trigger_hooks("PostCompletion", chunk)
                        if result is not None:
                            logger.error(f"PostCompletion钩子触发错误：{result}")
                            typer.echo(typer.style(result, fg=typer.colors.RED, bold=True))

                choices = getattr(chunk, "choices", None)
                if not choices:
                    continue
                delta = choices[0].delta
                if delta is None:
                    continue
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
            # 流式正文可能不以换行结尾；先 flush，保证它出现在工具日志/下一轮之前
            ui_redraw.flush_tokens()

            if not tool_calls_list:
                self.last_reply = collected_content or ""
                if final_turn and not self.last_reply:
                    self.last_reply = TURN_LIMIT_FALLBACK
                    typer.echo(typer.style(self.last_reply, fg=typer.colors.YELLOW))
                return

            if final_turn:
                #收尾轮不再执行工具，补回跳过结果保持 assistant/tool 消息契约
                for tc in tool_calls_list:
                    self.context.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": "已达到最大对话轮次，此工具调用被跳过。",
                    })
                self.last_reply = collected_content or TURN_LIMIT_FALLBACK
                if not collected_content:
                    typer.echo(typer.style(self.last_reply, fg=typer.colors.YELLOW))
                return

            used_todo = self._process_tool_calls(tool_calls_list, active_map)
            if used_todo:
                #打印在终端给用户看
                todo().render()
            else:
                todo().state.rounds_since_update += 1
                reminder = todo().reminder()
                if reminder:
                    #插入一条系统提示
                    self.context.append({"role": "user", "content": reminder})
            
            #每轮AgentLoop结束后插入todo列表，确保todo列表不会被压缩管线压缩掉
            self.context = todo().insert_todo_into_context(self.context)

    #提供外界获取上下文的接口
    def get_context(self):
        return self.context

    #提供外界初始化上下文的接口
    def set_context(self, context: list):
        self.context = context

    #初始化Agent,返回AgentRunner对象（代替构造函数）
    @classmethod
    def create_runner(cls, name: str, instructions: str | Callable[[], str], registry: ToolsRegistry, model: str = None):
        return cls(name=name, instructions=instructions, registry=registry, model=model)

#将工具函数的参数从dict类型转化为更方便人类阅读的dict类型
def _downgrade_multimodal(parts: list) -> list:
    """非视觉模型降级：剥离 image_url part，仅保留文本，避免 API 400 报错。

    只保留下唯一一条 text 提示，附带说明当前模型不支持视觉，图片内容已被省略。
    """
    text_parts = [
        p for p in parts
        if isinstance(p, dict) and p.get("type") == "text" and p.get("text")
    ]
    if text_parts:
        base = text_parts[0]["text"]
    else:
        base = ""
    return [{
        "type": "text",
        "text": base + "（当前模型不支持视觉能力，图片内容已省略。）"
    }]


def _brief_args(args: dict) -> str:
    parts = []
    for k, v in args.items():
        s = str(v)
        if len(s) > 80:
            s = s[:80] + "..."
        parts.append(f"{k}={s}")
    return ", ".join(parts)
