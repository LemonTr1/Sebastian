import os
import re
import shlex

from src.utils.exceptions import SecurityException

# Heuristic denylist only — not a shell parser. Real enforcement is sandbox + HITL.
DANGEROUS_PATTERNS = [
    r"mkfs\.\w+",
    r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*;\s*\}",
    r"dd\s+[^\n]*\bof\s*=",
    r">\s*/dev/sd[a-z]",
    r"chmod\s+777\s+/",
    r"wget\s+\S+\s+-O\s+/",
    r">\s*/etc/",
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

# 命令前缀中不影响语义的包装器，逐个剥离后再判断真实命令
_WRAPPERS = {"sudo", "doas", "command", "env", "busybox", "nohup", "time", "nice", "xargs"}
# 需要连带跳过参数值的包装器选项（如 sudo -u root、nice -n 10）
_WRAPPER_FLAGS_WITH_VALUE = {"-u", "-g", "-p", "-C", "-h", "-r", "-t", "-U", "-n"}
_SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
_DESTRUCTIVE = {"shred", "wipefs", "fdisk", "parted"}
# 危险目标：根目录、家目录、通配符（含空目标）
_DANGEROUS_TARGETS = {
    "/", "/*", "~", "~/", "~/*",
    "$HOME", "${HOME}", "$HOME/", "$HOME/*", "${HOME}/", "${HOME}/*",
    "*",
}


def _split_segments(command: str) -> list[str]:
    """按 shell 控制符拆段，便于逐段判断真实命令。"""
    return [seg for seg in re.split(r"(?:\|\||&&|[;|&\n])", command) if seg.strip()]


def _strip_wrappers(tokens: list[str]) -> list[str]:
    i = 0
    while i < len(tokens):
        name = os.path.basename(tokens[i]).lower()
        if name not in _WRAPPERS:
            break
        i += 1
        while i < len(tokens):
            tok = tokens[i]
            if tok.startswith("-"):
                i += 2 if tok in _WRAPPER_FLAGS_WITH_VALUE else 1
                continue
            if name == "env" and "=" in tok:
                i += 1
                continue
            break
    return tokens[i:]


def _flag_letters(tokens: list[str]) -> set[str]:
    letters = set()
    for tok in tokens:
        if tok.startswith("--"):
            continue
        if tok.startswith("-") and len(tok) > 1:
            letters.update(tok[1:].lower())
    return letters


def _is_dangerous_target(token: str) -> bool:
    cleaned = token.strip("'\"")
    if not cleaned:
        return True
    if cleaned in _DANGEROUS_TARGETS:
        return True
    # 形如 / 后的浅层通配，如 /*、/.*
    return cleaned.startswith("/*") and len(cleaned) <= 3


def _check_segment(segment: str) -> str | None:
    try:
        tokens = shlex.split(segment)
    except ValueError:
        tokens = segment.split()
    tokens = _strip_wrappers(tokens)
    if not tokens:
        return None

    name = os.path.basename(tokens[0]).lower()
    rest = tokens[1:]

    # sh -c "rm -rf /" 这类嵌套命令：递归检查载荷
    if name in _SHELLS and "-c" in rest:
        payload = " ".join(rest[rest.index("-c") + 1:])
        for sub in _split_segments(payload):
            hit = _check_segment(sub)
            if hit:
                return hit
        return None

    if name == "eval":
        return "eval 执行动态构造的命令"

    if name == "rm":
        letters = _flag_letters(rest)
        targets = [t for t in rest if not t.startswith("-")]
        recursive = "r" in letters or any(t.startswith("--recursive") for t in rest)
        force = "f" in letters or any(t == "--force" for t in rest)
        if any(t == "--no-preserve-root" for t in rest):
            return "rm --no-preserve-root"
        if recursive and force and (not targets or any(_is_dangerous_target(t) for t in targets)):
            return "递归强制删除根/家目录或通配目标"

    if name in _DESTRUCTIVE or name.startswith("mkfs"):
        return f"破坏性命令 {name}"

    if name == "find":
        if "-delete" in rest:
            return "find -delete"
        if "-exec" in rest:
            idx = rest.index("-exec")
            if idx + 1 < len(rest):
                sub = os.path.basename(rest[idx + 1]).lower()
                if sub in {"rm", "shred"}:
                    return "find -exec 删除"

    if name == "truncate":
        for i, tok in enumerate(rest):
            if tok == "-s" and i + 1 < len(rest) and rest[i + 1].lstrip("+") == "0":
                return "truncate 清零"
            if tok.startswith("-s0"):
                return "truncate 清零"

    if name == "git" and rest and rest[0] == "clean":
        letters = _flag_letters(rest[1:])
        if "f" in letters and ("d" in letters or "x" in letters):
            return "git clean 强制清理"

    if name in {"chown", "chmod"}:
        letters = _flag_letters(rest)
        targets = [t for t in rest if not t.startswith("-")][1:]  # 跳过模式/属主参数
        if "r" in letters and targets and any(_is_dangerous_target(t) for t in targets):
            return f"{name} 递归修改根/家目录权限"

    return None


def security_guard(command: str) -> None:
    # 去掉反斜杠转义（\\rm → rm），并合并空白
    normalized = re.sub(r"\s+", " ", command.replace("\\", ""))

    for seg in _split_segments(normalized):
        hit = _check_segment(seg)
        if hit:
            raise SecurityException(f"高危操作被系统拦截：{hit}")

    for p in DANGEROUS_PATTERNS:
        if re.search(p, normalized, re.IGNORECASE):
            raise SecurityException(f"高危操作被系统拦截：匹配模式 {p}")
