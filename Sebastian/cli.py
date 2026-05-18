"""CLI命令行入口"""
#禁用代理
import os
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['all_proxy'] = ''
#将.env配置加载到环境变量中
from dotenv import load_dotenv
load_dotenv(override=True)
from src.Agents import Brain_agent
import readline
import typer
import asyncio

app = typer.Typer(no_args_is_help=False ,help="AutomaticTaskAssistant")

@app.callback(invoke_without_command=True)
def setup(version: bool = typer.Option(False, "--version", "-v", help="Show version and exit")):
    if version:
        typer.echo("Automatic Task Assistant V 0.1")
        raise typer.Exit(code=0)
    else:
        try:
            asyncio.run(Brain_agent.chat())
        except Exception as e:
            typer.echo(f"Error: {str(e)}", err=True)
            raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
