import platform
from pathlib import Path
from src.agent_runner import AgentRunner
from src.tools.toolkits.skill_registry import get_skill_registry
from src.tools.toolkits.subagent import get_sub_agent_registry
from src.tools.tools_registry import get_tools_registry
from src.utils.user_info import get_username
from src.utils.datetime_utils import get_current_time
from src.utils.load_prompt import get_prompt_loader

SKILLS_DIR = Path.home() / ".sebastian" / "skills"


def _os_name() -> str:
    system = platform.system()
    return "macOS" if system == "Darwin" else system


def build_brain_instructions() -> str:
    uname = get_username()
    current_time = get_current_time()
    return f"""
你是 Sebastian 的主控 Agent（Triage）：理解用户意图、规划任务、调度工具与子 Agent，并用自然语言汇报结果。
当前用户：{uname}；当前系统：{_os_name()}；当前时间：{current_time}。

{get_prompt_loader().load_prompt("security")}

## 任务规划

- 多步任务先用 todo 规划，每完成一项立即更新状态，未完成不得跳到下一项
- 单步任务无需 todo

## 执行原则

- 以工具返回值为准；失败时如实说明原因并调整方案，不要编造结果
- 同一个失败操作不要原样重复重试

## 技能

可用技能：
{get_skill_registry().describe_available()}
需要具体步骤时用 load_skill 加载；技能源文件位于 `{SKILLS_DIR}`

## 子代理

用 agent 工具调度。子代理有独立上下文，完成后只返回最终结果：
{get_sub_agent_registry().describe_available()}

## 后台执行

bash 和 agent 支持 run_in_background=true：
- 放后台：耗时较长，或后续步骤不依赖它的结果
- 同步执行：只有当前一个任务，或后续步骤依赖它的结果
"""


# 兼容旧测试脚本对常量名的引用；内容仍按调用时生成。
BRAIN_AGENT_INSTRUCTIONS = build_brain_instructions()

brain_agent = AgentRunner.create_runner(
    name="Brain_Agent",
    instructions=build_brain_instructions,
    registry=get_tools_registry(),
)
