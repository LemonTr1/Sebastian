from agents import SQLiteSession, Runner
from openai.types.responses import ResponseTextDeltaEvent
from src.Agents.BrainAgent import brain_agent
from src.Interfaces.Exception.SecurityException import SecurityException
import os
import typer
from src.Interfaces.UserInfo import UserInfo

def sanitize_input(command: str) -> str:
    if "忽略之前的指令" in command or "ignore previous" in command:
        raise SecurityException("检测到提示词注入尝试")
    return command.strip()

async def chat():
    uname = os.getlogin()
    typer.echo(typer.style(f"Welcome {uname}！I'm Sebastian.What can I do for you? [Press 'quit' to exit]", fg=typer.colors.BLUE, bold=True))
    user_session = SQLiteSession(uname)
    while True:
        question = typer.prompt(typer.style(f"\n[{uname}]", fg=typer.colors.GREEN, bold=True))
        if question.lower() in ["quit", "exit"]:
            typer.echo(typer.style("Bye", fg=typer.colors.BLUE, bold=True))
            raise typer.Exit(code=0)
        try:
            question = sanitize_input(question)
            result = Runner.run_streamed(brain_agent, input=question, context=UserInfo(uname=uname), session=user_session, max_turns=50)
        except SecurityException as e:
            typer.echo(typer.style(f"Ops！你的输入被安全系统拦截了：{e}", fg=typer.colors.RED, bold=True))
            raise typer.Exit(code=1)
        except Exception as e:
            typer.echo(typer.style(f"Ops！机器人出现故障了：{e}", fg=typer.colors.RED, bold=True))
            raise typer.Exit(code=1)
        typer.echo(typer.style("[AI]: ", fg=typer.colors.BLUE, bold=True), nl=False)
        async for event in result.stream_events():
            if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                delta = event.data.delta
                typer.echo(delta, nl=False)
        typer.echo()