"""Agent-managed memory under ~/.sebastian/.memory/

MEMORY.md is the index. Sibling *.md files hold entries.
When disabled, the agent is never told this directory exists.
"""
from pathlib import Path
import json
from src.logs.app_log import get_log

logger = get_log()

SETTINGS = Path.home() / ".sebastian" / "settings.json"
MEMORY_DIR = Path.home() / ".sebastian" / ".memory"
MEMORY_INDEX = MEMORY_DIR / "MEMORY.md"

_INDEX_TEMPLATE = """# Memory index

List entries as `- [title](file.md) - one-line description`.
Actual notes live in sibling markdown files in this directory.
"""


class Memory:
    def __init__(self):
        self.IS_ALLOWED = False
        if SETTINGS.is_file():
            try:
                info = json.loads(SETTINGS.read_text(encoding="utf-8"))
                self.IS_ALLOWED = bool(info.get("memory", {}).get("enabled", False))
            except Exception as e:
                logger.warning(f"读取记忆开关失败，默认关闭: {e}")

    def is_allowed(self) -> bool:
        return self.IS_ALLOWED

    def is_memory_path(self, file_path: str | None) -> bool:
        """True if path resolves inside ~/.sebastian/.memory/ (memory mode on)."""
        if not file_path or not self.IS_ALLOWED:
            return False
        try:
            real = Path(file_path).expanduser().resolve()
            root = MEMORY_DIR.resolve()
            return real == root or real.is_relative_to(root)
        except (OSError, RuntimeError):
            return False

    def ensure_dir(self) -> None:
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        if not MEMORY_INDEX.is_file():
            MEMORY_INDEX.write_text(_INDEX_TEMPLATE, encoding="utf-8")

    def instruction_block(self) -> str:
        if not self.IS_ALLOWED:
            return ""
        self.ensure_dir()
        index = str(MEMORY_INDEX)
        folder = str(MEMORY_DIR)
        return f"""
        ## 长期记忆（已开启）
        用户通常不会手写记忆文件。不要在每轮开始时读取记忆。
        - 索引：`{index}`；条目在同目录 `{folder}` 的其它 markdown
        - 仅当本任务明确依赖「用户以前说过的偏好/约束」时，才 read 索引，再按需 read 条目
        - 用户在本轮明确说出稳定偏好或约束时：write 新 `.md` 到该目录，并 edit 更新 MEMORY.md 索引
        - 不要记对话流水或密钥；保持短小、条目化
        - 普通问答、一次性任务：直接做，不要碰记忆目录
        """

    def set_enabled(self, enabled: bool) -> None:
        self.IS_ALLOWED = enabled
        SETTINGS.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if SETTINGS.is_file():
            try:
                data = json.loads(SETTINGS.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = {}
        mem = data.get("memory") if isinstance(data.get("memory"), dict) else {}
        mem["enabled"] = enabled
        data["memory"] = mem
        SETTINGS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if enabled:
            self.ensure_dir()
        logger.info(f"记忆模式: {'on' if enabled else 'off'}")


MEMORY_SYSTEM = Memory()
