import re

DANGEROUS_PATTERNS = [
    r"rm\s+-rf\s+[/\\]",
    r"mkfs\.\w+",
    r":\(\)\{\s*:\|:\&\};:",
    r"dd\s+if=",
    r">\s*/dev/sd[a-z]",
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
]


def security_guard(command: str) -> None:
    for p in DANGEROUS_PATTERNS:
        if re.search(p, command, re.IGNORECASE):
            from src.utils.exceptions import SecurityException
            raise SecurityException(f"高危操作被系统拦截：匹配模式 {p}")
