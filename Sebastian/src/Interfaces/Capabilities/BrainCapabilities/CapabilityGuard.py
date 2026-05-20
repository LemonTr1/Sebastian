from agents import Agent, Runner
from src.Interfaces.Capabilities.BrainCapabilities.Capabilities import Capabilities, AGENT_CAPABILITIES
from src.Modules.CodeModules.CodeSession import code_session
from src.Modules.FileModules.FileSession import file_session
from src.Modules.WebModules.WebSession import web_session

class CapabilityGuard:
    #权限检查
    @staticmethod
    def check(agent_name: str, required_caps: Capabilities) -> None:
        allowed = AGENT_CAPABILITIES.get(agent_name)
        if allowed != required_caps:
            raise PermissionError(
                f"[权限不足] 当前Agent：{agent_name} 权限为 {allowed.name}，"
                f"实际需要权限：{required_caps.name}"
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
        if agent_name == "Code_Agent":
            session = code_session
        elif agent_name == "Web_Agent":
            session = web_session
        elif agent_name == "File_Agent":
            session = file_session
        result = await Runner.run(agent, input=task, max_turns=max_turns, session=session)
        return result.final_output
