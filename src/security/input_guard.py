import re
from typing import List


class InputSecurityEngine:
    _INJECTION_PATTERNS = [
        re.compile(r"(忽略|无视|忘记|不要|disregard|ignore|forget)\s+(你|上面|之前|所有|all|previous|above|system|prompt)", re.IGNORECASE),
        re.compile(r"(你现在是|扮演|act as|you are now|from now on)\s+(DAN|jailbreak|root|admin)", re.IGNORECASE),
        re.compile(r"(新指令|new instruction|system override|prompt override)", re.IGNORECASE),
        re.compile(r"(重新设定|覆盖|override|reset|reinitialize)\s+(角色|设定|指令|prompt|system)", re.IGNORECASE),
        re.compile(r"(忽略所有|ignore all)\s+(安全|限制|规则|约束|restriction|rule|constraint)", re.IGNORECASE),
        re.compile(r"(\.\./)+|(/\.\.)+"),
        re.compile(r"~[a-zA-Z]"),
    ]

    @classmethod
    def check(cls, text: str, username: str = None) -> List[str]:
        violations = []
        for pattern in cls._INJECTION_PATTERNS:
            if pattern.search(text):
                violations.append(f"检测到潜在注入攻击: {pattern.pattern[:60]}...")
        return violations
