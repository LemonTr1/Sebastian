"""REPL 斜杠命令清单与补全判定（纯逻辑，便于测试）。"""

SLASH_COMMANDS = {
    "/quit": "退出",
    "/exit": "退出",
    "/clear": "清空对话历史",
    "/compact": "手动压缩上下文",
    "/plan": "进入只读规划模式",
    "/build": "进入执行模式",
    "/auto": "进入免审批模式",
    "/memory on": "开启记忆",
    "/memory off": "关闭记忆",
}


def match_commands(text: str) -> list[str]:
    """返回 text 的全部前缀匹配命令；非斜杠输入返回空。"""
    if not text.startswith("/"):
        return []
    lowered = text.rstrip().lower()
    return [cmd for cmd in SLASH_COMMANDS if cmd.startswith(lowered)]


def resolve_enter(text: str) -> tuple[str, str | None]:
    """决定 Enter 的动作。

    - submit + 命令：唯一匹配时补全并直接执行（/pl -> /plan）
    - submit + 原文：普通输入、完整命令、未知斜杠命令
    - ignore：多个匹配且不是完整命令，保留菜单等待继续输入
    """
    if not text.startswith("/"):
        return "submit", text

    stripped = text.rstrip()
    matches = match_commands(stripped)
    if len(matches) == 1:
        return "submit", matches[0]
    if not matches or stripped.lower() in SLASH_COMMANDS:
        return "submit", stripped
    return "ignore", None
