class SessionIdContainer:
    def __init__(self, session_id: str = ""):
        self.session_id = session_id

    def get_session_id(self) -> str:
        return self.session_id

    def set_session_id(self, session_id: str):
        self.session_id = session_id

SESSION_ID_CONTAINER = SessionIdContainer()

def get_session_id_container() -> SessionIdContainer:
    return SESSION_ID_CONTAINER