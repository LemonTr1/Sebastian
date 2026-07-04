class TokenCaculator:
    def __init__(self):
        self.tokens_list = []

    def add_token(self, token: int):
        self.tokens_list.append(token)

    def accumulate_token(self):
        return sum(self.tokens_list)

    def clear(self):
        self.tokens_list = []

TOTAL_SESSION_TOKENS = TokenCaculator()

def get_total_session_tokens():
    return TOTAL_SESSION_TOKENS