"""斜杠命令匹配与 Enter 动作判定测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

PASS, FAIL = [], []

def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name} {detail}")


from src.utils.slash_commands import SLASH_COMMANDS, match_commands, resolve_enter

check("slash lists all commands", match_commands("/") == list(SLASH_COMMANDS), str(match_commands("/")))
check("/pl unique", match_commands("/pl") == ["/plan"], str(match_commands("/pl")))
check("memory commands removed", not any(c.startswith("/memory") for c in SLASH_COMMANDS), str(list(SLASH_COMMANDS)))
check("non slash none", match_commands("plan") == [], str(match_commands("plan")))
check("case insensitive", match_commands("/PL") == ["/plan"], str(match_commands("/PL")))
check("trailing newline ignored", match_commands("/plan\n") == ["/plan"], str(match_commands("/plan\n")))
check("trailing spaces ignored", match_commands("/plan   ") == ["/plan"], str(match_commands("/plan   ")))

check("enter unique submits full command", resolve_enter("/pl") == ("submit", "/plan"), str(resolve_enter("/pl")))
check("enter exact submits", resolve_enter("/plan") == ("submit", "/plan"), str(resolve_enter("/plan")))
check("enter ambiguous slash ignored", resolve_enter("/") == ("ignore", None), str(resolve_enter("/")))
check("enter normal text submits", resolve_enter("hello") == ("submit", "hello"), str(resolve_enter("hello")))
check("enter unknown slash submits",
      resolve_enter("/unknown") == ("submit", "/unknown"), str(resolve_enter("/unknown")))
check("enter trailing newline submits clean command",
      resolve_enter("/plan\n") == ("submit", "/plan"), str(resolve_enter("/plan\n")))
check("enter trailing spaces submits clean command",
      resolve_enter("/plan   ") == ("submit", "/plan"), str(resolve_enter("/plan   ")))

print(f"\n===== {len(PASS)} passed, {len(FAIL)} failed =====")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
