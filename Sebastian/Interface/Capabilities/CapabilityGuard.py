from agents import Agent, Runner
from Interface.Capabilities.Capabilities import Capabilities, AGENT_CAPABILITIES

class CapabilityGuard:
    #权限检查
    @staticmethod
    def check(agent_name: str, required_caps: Capabilities) -> None:
        allowed = AGENT_CAPABILITIES.get(agent_name)
        if allowed != required_caps:
            raise PermissionError(
                f"[权限不足] 当前Agent：{agent_name} 权限为 {allowed.name}，实际需要权限：{required_caps.name}"
            )

    @staticmethod
    async def run(
            agent: Agent,
            agent_name: str,
            task: str,
            required_caps: Capabilities,
            max_turns: int = 20
    )->str:
        CapabilityGuard.check(agent_name, required_caps)
        result = await Runner.run(agent, input=task, max_turns=max_turns)
        return result.final_output
