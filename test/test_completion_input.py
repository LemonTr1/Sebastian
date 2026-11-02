"""prompt_toolkit 斜杠补全测试：候选过滤、唯一前缀回车执行、非 TTY 回退。"""
import sys
import threading
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

PASS, FAIL = [], []

def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name} {detail}")


from src.utils import completion_input
from src.utils.completion_input import SlashCommandCompleter, build_key_bindings
from src.utils.slash_commands import SLASH_COMMANDS

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.document import Document
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput
    PT_AVAILABLE = True
except ImportError:
    PT_AVAILABLE = False


# ---- 1. 补全候选 ----
if PT_AVAILABLE:
    completer = SlashCommandCompleter()
    unique = list(completer.get_completions(Document("/pl", 3), None))
    check("completer unique", [c.text for c in unique] == ["/plan"], str([c.text for c in unique]))
    check("completer replaces whole prefix", unique and unique[0].start_position == -3, str(unique[0].start_position if unique else None))
    check("completer slash lists all", len(list(completer.get_completions(Document("/", 1), None))) == len(SLASH_COMMANDS))
    check("completer ignores normal text", list(completer.get_completions(Document("hello", 5), None)) == [])


# ---- 2. 真实 PromptSession：唯一前缀回车补全并执行 ----
def run_session(keys):
    with create_pipe_input() as pipe:
        pipe.send_text(keys)
        session = PromptSession(
            input=pipe,
            output=DummyOutput(),
            multiline=True,
            completer=SlashCommandCompleter(),
            complete_while_typing=True,
            reserve_space_for_menu=4,
            key_bindings=build_key_bindings(),
            history=InMemoryHistory(),
        )
        return session.prompt("> ")


def session_result(keys):
    out = []
    t = threading.Thread(target=lambda: out.append(run_session(keys)), daemon=True)
    t.start()
    t.join(timeout=5)
    return out[0] if out else None, t.is_alive()


if PT_AVAILABLE:
    result, hung = session_result("/pl\r")
    check("unique prefix submits completed command", result == "/plan" and not hung, f"{result!r} hung={hung}")

    result, hung = session_result("/plan\r")
    check("exact command submits", result == "/plan" and not hung, f"{result!r} hung={hung}")

    result, hung = session_result("hello\r")
    check("normal text submits", result == "hello" and not hung, f"{result!r} hung={hung}")

    result, hung = session_result("/auto\r")
    check("another exact command submits", result == "/auto" and not hung, f"{result!r} hung={hung}")

    result, hung = session_result("\x1b[200~line1\nline2\x1b[201~\r")
    check("bracketed multi-line paste preserved", result == "line1\nline2" and not hung, f"{result!r} hung={hung}")

    result, hung = session_result("line1\nline2\r")
    check("raw multi-line input preserved", result == "line1\nline2" and not hung, f"{result!r} hung={hung}")

    result, hung = session_result("\x1b[200~/plan\n\x1b[201~\r")
    check("bracketed command trailing newline cleaned", result == "/plan" and not hung, f"{result!r} hung={hung}")
else:
    print("SKIP: prompt_toolkit not installed")

# ---- 3. 非 TTY 回退 ----
with patch.object(completion_input, "_is_tty", return_value=False), \
     patch.object(completion_input.ui_redraw, "gated_input", return_value="fallback") as mock:
    out = completion_input.completing_input("> ")
check("non-tty falls back to gated_input", out == "fallback" and mock.called, repr(out))

print(f"\n===== {len(PASS)} passed, {len(FAIL)} failed =====")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
