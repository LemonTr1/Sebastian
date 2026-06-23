"""CLI命令行入口"""
import os

os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['all_proxy'] = ''

import re

from dotenv import load_dotenv, set_key
load_dotenv(override=True)

from src.hooks import hooks_registry

from src.agents.brain_agent import brain_agent
try:
    import readline
except ImportError:
    pass
import typer

app = typer.Typer(no_args_is_help=False, help="AutomaticTaskAssistant")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="Show version and exit")
):
    if version:
        typer.echo("Automatic Task Assistant V 0.2")
        raise typer.Exit(code=0)
    if ctx.invoked_subcommand is None:
        _run_chat()


def _run_chat():
    uname = os.getlogin()
    typer.echo(
        typer.style(
            f"Welcome {uname}！I'm Sebastian. [输入 'quit' 退出]",
            fg=typer.colors.BLUE,
            bold=True,
        )
    )

    while True:
        try:
            styled = typer.style(f"\n[{uname}]：", fg=typer.colors.GREEN, bold=True)
            prompt = re.sub(r'(\x1b\[[0-9;]*m)', r'\001\1\002', styled)
            question = input(prompt)
        except (EOFError, KeyboardInterrupt):
            typer.echo(typer.style("\nBye", fg=typer.colors.BLUE, bold=True))
            raise typer.Exit(code=0)

        if question.lower() in ("/quit", "/exit"):
            typer.echo(typer.style("Bye", fg=typer.colors.BLUE, bold=True))
            raise typer.Exit(code=0)

        if not question.strip():
            continue

        #进入AgentLoop前触发UserPromptSubmit钩子，检查输入安全性
        result = hooks_registry.get_hooks_registry().trigger_hooks("UserPromptSubmit", question, uname)
        if result is not None:
            typer.echo(typer.style(result, fg=typer.colors.RED, bold=True))
            continue

        try:
            typer.echo(
                typer.style("[Sebastian]: ", fg=typer.colors.BLUE, bold=True), nl=False
            )
            #进入AgentLoop
            result = brain_agent.run_stream(
                question,
                on_token=lambda token: typer.echo(token, nl=False),
            )
            typer.echo()
        except Exception as e:
            typer.echo(
                typer.style(
                    f"Ops！出现故障：{e}",
                    fg=typer.colors.RED,
                    bold=True,
                )
            )


@app.command()
def setup():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

    if not os.path.isfile(env_path):
        with open(env_path, "w") as f:
            pass

    model = typer.prompt("请输入模型名称 MODEL")
    api_key = typer.prompt("请输入模型的API_KEY", hide_input=True)
    base_url = typer.prompt("请输入模型的BASE_URL")

    set_key(env_path, "DEEPSEEK_MODEL", model)
    set_key(env_path, "DEEPSEEK_API_KEY", api_key)
    set_key(env_path, "DEEPSEEK_BASE_URL", base_url)

    typer.echo("\n配置保存成功")


if __name__ == "__main__":
    app()
