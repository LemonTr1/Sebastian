import os

def is_eval_mode() -> bool:
    return os.getenv("SEBASTIAN_EVAL", "").strip().lower() in {"1", "true", "yes", "on"}
