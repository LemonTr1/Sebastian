import asyncio
import os
from agents.sandbox.entries import LocalDir, File
from agents.sandbox.sandboxes import DockerSandboxClient, DockerSandboxClientOptions
from src.Models.models import deepseek_model
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['all_proxy'] = ''
from dotenv import load_dotenv
load_dotenv()
from pathlib import Path
from agents import Runner, ModelSettings, RunConfig, SQLiteSession
from agents.sandbox import SandboxAgent, Manifest, SandboxRunConfig, SandboxPathGrant
from agents.sandbox.capabilities import Shell
from docker import from_env

WORKSPACE = Path.home() / "桌面" / "exec"

async def main() -> None:
    user_session = SQLiteSession("user_id_1")
    manifest = Manifest(
        # root参数为沙箱内根目录名，一般单独不设置，默认为'/workspace'
        # 额外单独授权SandboxAgent可以引用LocalDir之外的目录
        extra_path_grants=(
            SandboxPathGrant(path=str(WORKSPACE.resolve())),
        ),
        entries={
            # 以绝对路径挂载外部文件,这里不是直接将外部文件放进沙箱，而是先在沙箱里创建名为`project`文件，然后将目标文件内容写入沙箱内文件
            "project": File(content=Path("/home/lem0ntr1/桌面/key").read_bytes()),
            # 设计哲学：LocalDir只能挂载当前运行目录的子目录，当前文件在UnitTests目录下，test_dir是UnitTests的一个子目录
            "dir": LocalDir(src=Path("test_dir")),
            # 挂载只读额外授权的目录
            "workdir": LocalDir(src=WORKSPACE)
        },
    )

    agent = SandboxAgent(
        name="Sandbox",
        model=deepseek_model,
        instructions="根据指令做出操作，并详细说明你具体做的每一步操作",
        default_manifest=manifest,
        capabilities=[Shell()],
        model_settings=ModelSettings(temperature=0.1, max_tokens=1000),
    )

    client = DockerSandboxClient(from_env())

    session = await client.create(manifest=manifest, options=DockerSandboxClientOptions(image="python:3.14-slim"))
    while True:
        question = input("请输入：")

        async with session:
            result = await Runner.run(
                agent,
                input=question,
                max_turns=20,
                session=user_session,
                run_config=RunConfig(
                    sandbox=SandboxRunConfig(
                        session=session,
                    )
                )
            )

            print(result.final_output)
if __name__ == "__main__":
    asyncio.run(main())