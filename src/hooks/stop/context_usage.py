from src.hooks.hooks_registry import get_hooks_registry
import typer
from src.config import MODEL, CONTEXT_WINDOW
from src.utils.compaction_pipeline import estimate_messages


def show_context_usage():
    """每轮对话结束（Stop事件）显示上下文占用情况，按预算阈值着色"""
    try:
        from src.agents.brain_agent import brain_agent
        context = brain_agent.get_context()
        used = estimate_messages(context)
        window = CONTEXT_WINDOW
    except Exception as e:
        return f"上下文占用统计出错：{e}"

    ratio = used / window if window else 0
    if ratio >= 0.95:
        color = typer.colors.RED
    elif ratio >= 0.75:
        color = typer.colors.YELLOW
    else:
        color = typer.colors.WHITE

    typer.echo(typer.style(
        f"\n[上下文占用：{used:,} / {window:,} tokens ({ratio:.1%})]",
        fg=color,
    ))
    return None


#注册钩子
get_hooks_registry().register_hook("Stop", show_context_usage)
