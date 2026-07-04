from src.hooks.hooks_registry import get_hooks_registry
from src.tokens.tokens_caculator import get_total_session_tokens

def calculate_tokens(primitive_response):
    try:
        usage = primitive_response.usage.total_tokens
    except Exception as e:
        return f"Error: {e}"
    token_calculator = get_total_session_tokens()
    token_calculator.add_token(usage)
    return None

#注册钩子
get_hooks_registry().register_hook("PostCompletion", calculate_tokens)
