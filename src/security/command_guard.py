import re

from src.utils.exceptions import SecurityException

# Heuristic denylist only — not a shell parser. Real enforcement is sandbox + HITL.
DANGEROUS_PATTERNS = [
    r"rm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+(/|~|\$home|\$\{home\}|\*)",
    r"rm\s+-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*\s+(/|~|\$home|\$\{home\}|\*)",
    r"mkfs\.\w+",
    r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*;\s*\}",
    r"dd\s+if=",
    r"dd\s+[^\n]*\bof\s*=",
    r">\s*/dev/sd[a-z]",
    r"chmod\s+-R",
    r"chmod\s+777\s+/",
    r"wget\s+\S+\s+-O\s+/",
    r">\s*/etc/",
    r"eval\s+",
    r"exec\s*\(",
    r"__import__\s*\(\s*['\"]os['\"]",
    r"subprocess\s*\.\s*call",
    r"os\s*\.\s*system",
    r":fork|fork\s*bomb",
    r"shutdown\s+-",
    r"reboot\s+-",
    r"init\s+[06]",
    r"iptables\s+-F",
    r"(curl|wget).*\|\s*(ba)?sh\b",
    r"/dev/tcp/",
    r"\bnc(at)?\s+-[^\s]*e",
]


def security_guard(command: str) -> None:
    normalized = re.sub(r"\s+", " ", command)
    for p in DANGEROUS_PATTERNS:
        if re.search(p, normalized, re.IGNORECASE):
            raise SecurityException(f"高危操作被系统拦截：匹配模式 {p}")
