"""Agent 运行模式（Plan / Build）。

- 登录默认 Build：Brain_Agent 拥有全部工具
- /plan 进入 Plan：只读规划模式，仅白名单工具可用（schema 移除 + 提示词引导）
- /build 退出 Plan：恢复全部工具
- 模式运行期有效，不随会话持久化
"""
from src.logs.app_log import get_log

logger = get_log()


class AgentMode:
    BUILD = "build"
    PLAN = "plan"

    # Plan 模式可用工具白名单（其余工具在 Plan 下被移除 schema 并拒绝执行）
    PLAN_ALLOWED_TOOLS = frozenset({
        "read", "glob", "grep", "ls", "todo",
        "web_search", "web_fetch", "load_skill", "list_crons",
    })

    def __init__(self):
        self._mode = self.BUILD

    def get(self) -> str:
        return self._mode

    def set(self, mode: str):
        self._mode = mode
        logger.info(f"[mode] 切换至 {mode} 模式")

    def is_plan(self) -> bool:
        return self._mode == self.PLAN

    def allowed_tools(self) -> frozenset:
        return self.PLAN_ALLOWED_TOOLS

    def forbidden_tools(self, all_tools) -> list:
        """从 Agent 实际工具集推导 Plan 模式禁用集"""
        return sorted(set(all_tools) - set(self.PLAN_ALLOWED_TOOLS))

    def describe(self, all_tools) -> str:
        """生成注入 system 提示词的 Plan 模式说明"""
        allowed = sorted(self.PLAN_ALLOWED_TOOLS)
        forbidden = self.forbidden_tools(all_tools)
        return f"""
## 当前模式：Plan（只读规划模式）
你当前处于 Plan 模式，只做调研、分析与规划，绝不执行任何修改性操作。

【可用工具】{", ".join(allowed)}
【禁止工具】{", ".join(forbidden)}

- 禁止执行命令、写文件、改文件、调度/取消定时任务、派发子 Agent
- 需要的执行类操作只能写进计划，等用户切换到 Build 模式后再执行

【行为要求】
1. 以思考与规划为主：先充分调研（read/glob/grep/ls/web_search/web_fetch/load_skill），再产出清晰、可执行的计划；用 todo 维护计划步骤
2. 不得声称已执行任何操作，不得伪造工具结果
3. 计划完成后必须主动询问用户下一步：立即退出 Plan 模式并执行（用户输入 /build），还是修改当前计划（请用户说明要改什么）；向用户确认计划的可行性，等待用户决定，不得自行推进执行
4. 用户输入 /build 即可退出 Plan 模式
""".strip()


AGENT_MODE = AgentMode()
