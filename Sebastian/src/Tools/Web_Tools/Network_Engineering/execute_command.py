import json
import typer
from agents import ModelSettings
from agents.sandbox import SandboxAgent
from agents.run_config import SandboxRunConfig, RunConfig
from agents.sandbox.sandboxes import DockerSandboxClient, DockerSandboxClientOptions
from agents.sandbox.capabilities import Shell
from agents import function_tool, Runner
from src.Interfaces.Docker.ensure_docker import ensure_image
from src.Interfaces.Exception.ImageNotFoundException import ImageNotFoundException
from docker import from_env
from src.Models.models import deepseek_model

sandbox_agent = SandboxAgent(
    name="Sandbox",
    model=deepseek_model,
    instructions=(
        """
        你的任务是根据上级Agent命令，组合各种Shell命令完成网络扫描，网络分析，数字足迹和开源情报收集工作
        除了常见的Shell命令，支持的网络扫描工具有：nmap, tshark, tcpdump, whois, dnsutils, ca-certificates, libimage-exiftool-perl
        sherlock-project, holehe, maigret, socialscan, infoooze，你可以组合使用这些工具完成上级Agent指令，必须完整返回执行结果
        """
    ),
    capabilities=[Shell()],
    model_settings=ModelSettings(temperature=0.1, max_tokens=500),
)

@function_tool
async def execute_command(command: str)->str:
    """
    在终端执行Shell命令进行网络扫描查询
    除了常见的Shell命令，支持的网络扫描工具有：nmap, tshark, tcpdump, whois, dnsutils, ca-certificates, libimage-exiftool-perl
    sherlock-project, holehe, maigret, socialscan, infoooze
    Args:
        command: str类型，表示Shell命令或代码
    Returns:
        json结构的字符串
        {
            "success": 执行成功为True,失败为False
            "summary": 执行概要，如果执行失败则为错误信息
            "result": 执行的完整结果
        }
    """
    try:
        image = ensure_image("sebastian:local")
    except ImageNotFoundException as e:
        typer.echo(typer.style(f"镜像拉取失败:{str(e)}", fg=typer.colors.RED))
        return json.dumps({
            "success": False,
            "summary": f"沙箱环境初始化失败：{str(e)}",
            "result": None
        })

    typer.echo(typer.style(f"[执行中]正在使用网络工具执行命令：{command[:20]}...", fg=typer.colors.WHITE))
    try:
        result = await Runner.run(
            sandbox_agent,
            input=f"执行代码或命令：{command}，并完整返回输出结果",
            max_turns=50,
            run_config=RunConfig(
                sandbox=SandboxRunConfig(
                    client=DockerSandboxClient(from_env()),
                    options=DockerSandboxClientOptions(image=image)
                )
            )
        )
    except Exception as e:
        typer.echo(
            typer.style(f"[execute_command]执行代码：`{command[:20]}...`失败:{e}", fg=typer.colors.RED))
        return json.dumps({
            "success": False,
            "summary": f"工具执行代码：{command}失败:{e}",
            "result": None
        })

    typer.echo(typer.style(f"[Success]代码执行成功!", fg=typer.colors.GREEN))
    return json.dumps({
        "success": True,
        "summary": "工具执行成功",
        "result": result.final_output
    })




