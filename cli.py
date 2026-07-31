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
from src.utils.user_info import get_username
try:
    import readline
except ImportError:
    pass
import typer
from src.logs.app_log import get_log
from src.utils.session_id_container import get_session_id_container
from pathlib import Path
import time
from datetime import datetime
import json
from src.utils.compaction_pipeline import compact_history

logger = get_log()

app = typer.Typer(no_args_is_help=False, help="AutomaticTaskAssistant")

AGENT_SESSION_DIR = Path.home() / ".sebastian" / "session"

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="Show version and exit"),
    session_id: str = typer.Option(None, "--session", "-s", help="Use Session ID To Restore The Conversation")
):
    if version:
        typer.echo("Automatic Task Assistant V 0.2")
        raise typer.Exit(code=0)
    if ctx.invoked_subcommand is None:
        # 类似于：20260730-2346-a7f3
        if not session_id:
            session_id = datetime.now().strftime("%Y%m%d-%H%M") + "-" + hex(int(time.time()))[-4:]
        _run_chat(session_id)

#进入AgentLoop前还原上下文内容
def restore_context(session_id: str) -> str | None:
    session_file = AGENT_SESSION_DIR / f"{session_id}.jsonl"
    #如果存在保存过的历史会话文件
    if session_file.is_file():
        try:
            with session_file.open("r", encoding="utf-8") as f:
                context = [json.loads(line) for line in f if line.strip()]
            brain_agent.set_context(context)
            typer.echo(typer.style(f"已恢复会话：{session_id}", fg=typer.colors.WHITE, bold=True))
        except json.JSONDecodeError as e:
            logger.error(f"错误：无法解析会话文件 {session_file}：{e}")
            typer.echo(typer.style(f"错误：无法解析会话文件 {session_file}：{e}", fg=typer.colors.RED, bold=True))
        except Exception as e:
            logger.error(f"恢复会话失败：{e}")
            typer.echo(typer.style(f"恢复会话失败：{e}", fg=typer.colors.RED, bold=True))

        return None

    #如果不存在该session_id,则重置session_id的值并返回
    session_id = datetime.now().strftime("%Y%m%d-%H%M") + "-" + hex(int(time.time()))[-4:]
    return session_id

def clear_session(keep: int = 10):
    #保留最近10个会话文件，删除旧的
    session_files = sorted(AGENT_SESSION_DIR.glob("*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True)
    if len(session_files) > keep:
        for old_file in session_files[keep:]:
            try:
                old_file.unlink()
                logger.info(f"已删除旧会话文件：{old_file}")
            except Exception as e:
                logger.error(f"删除旧会话文件失败 {old_file}：{e}")
                typer.echo(typer.style(f"删除旧会话文件失败 {old_file}：{e}", fg=typer.colors.RED, bold=True))

#保存会话
def save_session(context: list, session_id: str):
    session_file = AGENT_SESSION_DIR / f"{session_id}.jsonl"

    try:
        #清空覆写
        with session_file.open("w", encoding="utf-8") as f:
            for message in context:
                if message["role"] == "system":
                    continue
                f.write(json.dumps(message, ensure_ascii=False) + "\n")

        typer.echo(typer.style(f"会话已保存，使用：sebastian -s {session_id} 即可恢复会话", fg=typer.colors.WHITE, bold=True))
    except PermissionError:
        logger.error(f"错误：没有权限写入：{session_file}")
        typer.echo(typer.style(f"错误：没有权限写入：{session_file}", fg=typer.colors.RED, bold=True))
    except OSError as e:
        logger.error(f"错误：无法写入文件 {session_file}：{e}")
        typer.echo(typer.style(f"错误：无法写入文件 {session_file}：{e}", fg=typer.colors.RED, bold=True))
    except Exception as e:
        logger.error(f"保存会话失败：{e}")
        typer.echo(typer.style(f"保存会话失败：{e}", fg=typer.colors.RED, bold=True))

    #保留最近10个会话文件，删除旧的
    clear_session()

def _run_chat(session_id: str):
    uname = get_username()
    logger.info(f"{uname} 登陆系统")
    typer.echo(
        typer.style(
            f"Welcome {uname}！I'm Sebastian. [输入 'quit' 退出]",
            fg=typer.colors.BLUE,
            bold=True,
        )
    )

    #初始化重要递归目录：~/.sebastian/session
    if not Path.is_dir(AGENT_SESSION_DIR):
        Path(AGENT_SESSION_DIR).mkdir(parents=True, exist_ok=True)

    #根据session_id初始化上下文内容
    restored = restore_context(session_id)
    if restored is not None:
        session_id = restored

    get_session_id_container().set_session_id(session_id)

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
            #保存对话历史
            session = brain_agent.get_context()
            save_session(session, session_id)
            logger.info(f"{uname} 已成功保存会话并登出系统")
            raise typer.Exit(code=0)

        if question.lower() == "/clear":
            brain_agent.set_context([])
            logger.info(f"{uname} 手动清空所有历史对话")
            typer.echo(typer.style("已清空所有历史对话", fg=typer.colors.GREEN, bold=True))
            continue

        if question.lower() == "/compact":
            brain_agent.set_context(compact_history(brain_agent.get_context()))
            logger.info(f"{uname} 手动压缩历史对话")
            typer.echo(typer.style("已压缩历史对话", fg=typer.colors.GREEN, bold=True))
            continue

        if not question.strip():
            continue

        #进入AgentLoop前触发UserPromptSubmit钩子，检查输入安全性
        result = hooks_registry.get_hooks_registry().trigger_hooks("UserPromptSubmit", question, uname)
        if result is not None:
            logger.error(f"UserPromptSubmit钩子触发错误：{result}")
            typer.echo(typer.style(result, fg=typer.colors.RED, bold=True))
            continue

        try:
            typer.echo(
                typer.style("[Sebastian]: ", fg=typer.colors.BLUE, bold=True), nl=False
            )
            #进入AgentLoop
            brain_agent.run_stream(
                question,
                on_token=lambda token: typer.echo(token, nl=False),
            )
            result = hooks_registry.get_hooks_registry().trigger_hooks("Stop")
            if result is not None:
                logger.error(f"Stop钩子触发错误：{result}")
                typer.echo(typer.style(result, fg=typer.colors.RED, bold=True))

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
