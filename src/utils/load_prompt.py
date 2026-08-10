from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

class PromptLoader:
    def __init__(self):
        self.prompt_file_list = list(PROMPTS_DIR.glob("*.md"))

    def load_prompt(self, prompt_file_name: str) -> str:
        for f in self.prompt_file_list:
            if f.name == prompt_file_name + ".md":
                return f.read_text(encoding="utf-8")
        return "<SYSTEN_REMINDER>prompt加载失败，立即向用户反馈</SYSTEM_REMINDER>"

PROMPT_LOADER = PromptLoader()

def get_prompt_loader() -> PromptLoader:
    return PROMPT_LOADER

