import json
from agents import ModelSettings
from agents.sandbox import SandboxAgent, Manifest, SandboxPathGrant
from agents.run_config import SandboxRunConfig, RunConfig
from agents.sandbox.entries import LocalDir, File
from agents.sandbox.sandboxes import DockerSandboxClient, DockerSandboxClientOptions
from agents.sandbox.capabilities import Shell
from agents import function_tool, Runner
import typer
from Interface.Docker.ensure_docker import ensure_image
from Interface.Exception.ImageNotFoundException import ImageNotFoundException
from Interface.SafePath import resolve_safe_path
from Interface.Exception.SecurityException import SecurityException
from docker import from_env
import os
from models import deepseek_model
from pathlib import Path

sandbox_agent = SandboxAgent(
    name="Sandbox",
    model=deepseek_model,
    instructions=(
        """
        你的任务是阅读分析代码文件的安全性，目标就是/workspace目录下唯一的那个文件(如果是目录则递归阅读分析里面所有的文件)，并返回安全性分析，如果存在有安全性风险的文件需明确指出
        **禁止执行项目中的任何可执行文件**
        """
    ),
    capabilities=[Shell()],
    model_settings=ModelSettings(temperature=0.1, max_tokens=300),
)

@function_tool
async def review_tool(path: str)->str:
    """
    在隔离的沙箱环境中对代码文件内容进行安全性分析
    Args:
        path: str类型，表示代码文件路径
    Returns:
        json结构的字符串
        {
            "success": 工具执行成功为True,失败为False
            "summary": 工具执行概要，如果执行失败则为错误信息
            "result": 安全性分析的完整结果
        }
    """
    try:
        #要求返回解析符号链接后的真实路径
        path = resolve_safe_path(path, "real")
    except SecurityException as e:
        return json.dumps({
            "success": False,
            "summary": str(e),
            "result": None
        })

    try:
        image = ensure_image("python:3.14-slim")
    except ImageNotFoundException as e:
        return json.dumps({
            "success": False,
            "summary": f"沙箱环境初始化失败：{str(e)}",
            "result": None
        })

    if os.path.isdir(path):
        manifest = Manifest(
            #额外授权目录
            extra_path_grants=(
                SandboxPathGrant(path=str(path), read_only=True),
            ),
            entries={
                #挂载点：沙箱内/workspace/{Path(path).name}
                f"{Path(path).name}": LocalDir(src=Path(path)),
            }
        )
    else:
        manifest = Manifest(
            entries={
                f"{Path(path).name}": File(content=Path(path).read_bytes()),
            }
        )

    sandbox_agent.default_manifest = manifest

    typer.echo(typer.style(f"[执行中]正在沙箱环境中审核代码文件：{path}",fg=typer.colors.WHITE))
    try:
        result = await Runner.run(
            sandbox_agent,
            input=f"分析/workspace/{Path(path).name}代码文件的安全性，严禁执行任何可执行文件",
            max_turns=20,
            run_config=RunConfig(
                sandbox=SandboxRunConfig(
                    client=DockerSandboxClient(from_env()),
                    options=DockerSandboxClientOptions(image=image)
                )
            )
        )
    except Exception as e:
        typer.echo(typer.style(f"[review_tool]工具分析代码文件：{path}失败",fg=typer.colors.RED))
        return json.dumps({
            "success": False,
            "summary": f"工具分析代码文件：{path}失败:{e}",
            "result": None
        })

    typer.echo(typer.style(f"[Success]代码文件：{path}审核完成",fg=typer.colors.GREEN))
    return json.dumps({
        "success": True,
        "summary": "工具执行成功",
        "result": result.final_output
    })