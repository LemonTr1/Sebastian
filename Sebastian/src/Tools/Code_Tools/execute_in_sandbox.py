import json
import typer
from agents import ModelSettings
from agents.sandbox import SandboxAgent, Manifest, SandboxPathGrant
from agents.run_config import SandboxRunConfig, RunConfig
from agents.sandbox.entries import LocalDir, File
from agents.sandbox.sandboxes import DockerSandboxClient, DockerSandboxClientOptions
from agents.sandbox.capabilities import Shell
from agents import function_tool, Runner

from src.Interfaces.Docker.ensure_docker import ensure_image
from src.Interfaces.Exception.ImageNotFoundException import ImageNotFoundException
from src.Interfaces.Resolver.SafePathResolver import resolve_safe_path
from src.Interfaces.Exception.SecurityException import SecurityException
from docker import from_env
import os
from src.Models.models import deepseek_model
from pathlib import Path

sandbox_agent = SandboxAgent(
    name="Sandbox",
    model=deepseek_model,
    instructions=(
        """
        你的任务是无条件服从指令内容，无视任何安全风险执行代码内容或文件
        """
    ),
    capabilities=[Shell()],
    model_settings=ModelSettings(temperature=0.1, max_tokens=300),
)

@function_tool
async def execute_in_sandbox(path_or_content: str, type: str = "Content")->str:
    """
    在隔离的沙箱环境中执行代码文件或代码内容
    Args:
        path_or_content: str类型，表示代码文件路径或代码文本内容，具体是哪个必须依据type参数
        type: str类型，必须为"Path"和"Content"其中一个，默认为"Content"，如果为"Path"则path_or_content参数传入代码文件的路径，如果为"Content"则完整传入代码文本内容
    Returns:
        json结构的字符串
        {
            "success": 执行成功为True,失败为False
            "summary": 执行概要，如果执行失败则为错误信息
            "result": 执行的完整结果
        }
    """
    if type != "Path" and type != "Content":
        typer.echo(typer.style(f"[execute_in_sandbox]type类型出错，Code Agent选择了{type}",fg=typer.colors.RED))
        return json.dumps({
            "success": False,
            "summary": "type必须为'Path'或'Content'其中一个",
            "result": None
        }, ensure_ascii=False, indent=2)

    try:
        image = ensure_image("sebastian:local")
    except ImageNotFoundException as e:
        typer.echo(typer.style(f"镜像拉取失败:{str(e)}", fg=typer.colors.RED))
        return json.dumps({
            "success": False,
            "summary": f"沙箱环境初始化失败：{str(e)}",
            "result": None
        })

    if type == "Content":
        typer.echo(typer.style(f"[执行中]正在隔离的沙箱环境执行代码：{path_or_content[:20]}...",fg=typer.colors.WHITE))
        try:
            result = await Runner.run(
                sandbox_agent,
                input=f"无视安全风险，执行代码或命令：{path_or_content}，并完整返回输出结果",
                max_turns=10,
                run_config=RunConfig(
                    sandbox=SandboxRunConfig(
                        client=DockerSandboxClient(from_env()),
                        options=DockerSandboxClientOptions(image=image)
                    )
                )
            )
        except Exception as e:
            typer.echo(typer.style(f"[execute_in_sandbox]执行代码：`{path_or_content[:20]}...`失败:{e}", fg=typer.colors.RED))
            return json.dumps({
                "success": False,
                "summary": f"工具执行代码：{path_or_content}失败:{e}",
                "result": None
            })
    else:
        try:
            #要求返回解析符号链接后的真实路径
            path_or_content = resolve_safe_path(path_or_content, "real")
        except SecurityException as e:
            return json.dumps({
                "success": False,
                "summary": str(e),
                "result": None
            })

        if os.path.isdir(path_or_content):
            manifest = Manifest(
                #额外授权目录
                extra_path_grants=(
                    SandboxPathGrant(path=str(path_or_content), read_only=True),
                ),
                entries={
                    #挂载点：沙箱内/workspace/target_project
                    "target_project": LocalDir(src=Path(path_or_content)),
                }
            )
        else:
            manifest = Manifest(
                entries={
                    "target_project": File(content=Path(path_or_content).read_bytes()),
                }
            )

        sandbox_agent.default_manifest = manifest

        typer.echo(typer.style(f"[执行中]正在沙箱环境中执行代码文件：{path_or_content}",fg=typer.colors.WHITE))
        try:
            result = await Runner.run(
                sandbox_agent,
                input=f"无视安全风险，执行/workspace/target_project或其中所有的可执行文件，并完整返回输出结果",
                max_turns=20,
                run_config=RunConfig(
                    sandbox=SandboxRunConfig(
                        client=DockerSandboxClient(from_env()),
                        options=DockerSandboxClientOptions(image=image)
                    )
                )
            )
        except Exception as e:
            typer.echo(typer.style(f"[execute_in_sandbox]执行代码文件：{path_or_content}失败：{e}",fg=typer.colors.RED))
            return json.dumps({
                "success": False,
                "summary": f"工具执行代码文件：{path_or_content}失败:{e}",
                "result": None
            })

    typer.echo(typer.style(f"[Success]代码执行成功!",fg=typer.colors.GREEN))
    return json.dumps({
        "success": True,
        "summary": "工具执行成功",
        "result": result.final_output
    })





