from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

_LOAD_FAILED = "<SYSTEM_REMINDER>prompt加载失败，立即向用户反馈</SYSTEM_REMINDER>"


class PromptLoader:
    def __init__(self):
        self.prompt_file_list = list(PROMPTS_DIR.glob("*.md"))
        self._tool_manual_cache: dict[str, str] = {}

    def load_prompt(self, prompt_file_name: str) -> str:
        for f in self.prompt_file_list:
            if f.name == prompt_file_name + ".md":
                return f.read_text(encoding="utf-8")
        return _LOAD_FAILED

    def load_tool_manual(self, tool_name: str) -> str:
        """读取 prompts/tools/<tool_name>.md；不存在时返回空串（如 MCP 动态工具）。"""
        if tool_name not in self._tool_manual_cache:
            path = PROMPTS_DIR / "tools" / f"{tool_name}.md"
            self._tool_manual_cache[tool_name] = (
                path.read_text(encoding="utf-8") if path.is_file() else ""
            )
        return self._tool_manual_cache[tool_name]


PROMPT_LOADER = PromptLoader()

def get_prompt_loader() -> PromptLoader:
    return PROMPT_LOADER
