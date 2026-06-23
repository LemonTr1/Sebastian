class HooksRegistry:
    def __init__(self):
        self.hooks = {"UserPromptSubmit": [], "PreToolUse": [], "PostToolUse": [], "Stop": []}

    def register_hook(self, event: str, callback):
        self.hooks[event].append(callback)

    def trigger_hooks(self, event: str, *args):
        for callback in self.hooks[event]:
            result = callback(*args)
            if result is not None:
                return result
        return None

HOOKS_REGISTRY = HooksRegistry()

def get_hooks_registry():
    return HOOKS_REGISTRY