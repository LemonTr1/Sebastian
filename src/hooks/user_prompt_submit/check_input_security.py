from src.security.input_guard import InputSecurityEngine
from src.hooks.hooks_registry import get_hooks_registry

def check_input_security_hook(question: str, uname: str):
    """Check Security of Input"""
    violations = InputSecurityEngine.check(question, username=uname)
    if violations:
        return f"安全拦截：{'; '.join(violations)}"
    return None

#注册钩子
get_hooks_registry().register_hook("UserPromptSubmit", check_input_security_hook)

