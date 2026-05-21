import os
import typer
from agents import Agent, Runner
from agents.run_config import SandboxRunConfig, RunConfig
from agents.sandbox import SandboxAgent, Manifest, SandboxPathGrant
from agents.sandbox.entries import LocalDir, File
from src.Interfaces.Capabilities.BrainCapabilities.Capabilities import Capabilities, AGENT_CAPABILITIES
from src.Interfaces.Docker.EnsureDocker import ensure_image
from src.Interfaces.Exception.ImageNotFoundException import ImageNotFoundException
from src.Modules.CodeModules.CodeSession import get_code_session, get_code_session_lock
from src.Modules.FileModules.FileSession import get_file_session
from src.Modules.WebModules.WebSession import get_web_session
from src.Modules.CodeModules.SandboxSessionFactory import SandboxSessionFactory
from pathlib import Path

# 简单的类型到权限映射
TYPE_TO_CAPABILITY = {
    "File": Capabilities.FILE_EXECUTE,
    "Code": Capabilities.CODE_EXECUTE,
    "Web": Capabilities.WEB_EXECUTE,
}

# 类型到Agent名称映射
TYPE_TO_AGENT_NAME = {
    "File": "File_Agent",
    "Code": "Code_Agent",
    "Web": "Web_Agent",
}

class CapabilityGuard:
    # 权限检查 - 直接用 type 字符串
    @staticmethod
    def check(agent_name: str, task_type: str) -> None:
        required_caps = TYPE_TO_CAPABILITY[task_type]
        allowed = AGENT_CAPABILITIES.get(agent_name)
        if allowed != required_caps:
            raise PermissionError(
                f"[权限不足] 当前Agent：{agent_name} 权限为 {allowed.name}，"
                f"实际需要权限：{required_caps.name}"
            )

    @staticmethod
    async def run(
            agent: Agent | SandboxAgent,
            task_type: str,
            task: str,
            max_turns: int = 20,
            path: str = "None"
    )->str:
        agent_name = TYPE_TO_AGENT_NAME[task_type]
        CapabilityGuard.check(agent_name, task_type)
        
        if task_type == "Code":
            #对CodeAgent共享Session缓冲区读取必须互斥，所以实际上还是只能串行执行Shell命令或代码
            async with get_code_session_lock():
                session = get_code_session()
                # 检查本地镜像是否正常运行
                try:
                    ensure_image("sebastian:local")
                except ImageNotFoundException as e:
                    raise ImageNotFoundException(str(e))
                # 挂载再运行
                manifest = Manifest()
                if path != "None":
                    if os.path.isdir(path):
                        manifest = Manifest(
                            root=str(Path(path).parent),
                            # 额外授权目录
                            extra_path_grants=(
                                SandboxPathGrant(path=str(path), read_only=True),
                            ),
                            entries={
                                # 挂载点
                                f"{str(Path(path).name)}": LocalDir(src=Path(path)),
                            }
                        )
                    else:
                        manifest = Manifest(
                            root=str(Path(path).parent),
                            entries={
                                f"{str(Path(path).name)}": File(content=Path(path).read_bytes()),
                            }
                        )
                run_session = await SandboxSessionFactory.get_session(manifest)
                typer.echo(typer.style(f"正在Docker容器中执行代码...",fg=typer.colors.WHITE))
                async with run_session:
                    result = await Runner.run(
                        agent,
                        input=task,
                        max_turns=max_turns,
                        session=session,
                        run_config=RunConfig(
                            sandbox=SandboxRunConfig(
                                session=run_session
                            )
                        )
                    )
                    return result.final_output
        elif task_type == "Web":
            session = get_web_session()
        elif task_type == "File":
            session = get_file_session()
        result = await Runner.run(agent, input=task, max_turns=max_turns, session=session)
        return result.final_output
