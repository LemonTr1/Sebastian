from src.hooks.hooks_registry import get_hooks_registry
import typer
from src.utils.tokens_caculator import get_total_session_tokens

def summarize_tokens():
    typer.echo(typer.style(f"\n[本轮Token消耗：{get_total_session_tokens().accumulate_token()}]",fg=typer.colors.WHITE))
    #清理
    get_total_session_tokens().clear()
    return None

#注册工具
get_hooks_registry().register_hook("Stop", summarize_tokens)
