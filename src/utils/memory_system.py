from pathlib import Path
import json
import re
import time
import typer
from src.logs.app_log import get_log
from src.config import get_client, MODEL

logger = get_log()


def _create_completion(messages: list, max_tokens: int):
    """记忆相关API调用：优先关闭推理模型的思考（deepseek-v4-flash 会把max_tokens
    全部消耗在思维链上导致content为空），后端拒绝该参数时自动回退到普通调用
    （兼容 OpenAI 官方 API / Ollama / vLLM 等严格校验参数的端点）"""
    try:
        return get_client().chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=max_tokens,
            extra_body={"thinking": {"type": "disabled"}},
        )
    except Exception:
        logger.warning("后端拒绝 thinking 参数，回退到普通调用")
        return get_client().chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=max_tokens,
        )


class Memory:
    def __init__(self):
        self.CONSOLIDATE_THRESHOLD = 10
        self.MEMORY_TYPES: list[str] = ["user", "feedback", "project", "reference"]
        self.MEMORY_DIR = Path.home() / ".sebastian" / ".memory"
        if not self.MEMORY_DIR.is_dir():
            self.MEMORY_DIR.mkdir(exist_ok=True, parents=True)
        self.MEMORY_INDEX = self.MEMORY_DIR / "MEMORY.md"
        if not self.MEMORY_INDEX.is_file():
            #Create empty index file
            self.MEMORY_INDEX.write_text("", encoding="utf-8")

    def _parse_frontmatter(self, text: str) -> tuple[dict, str]:
        """Extract YAML frontmatter"""
        if not text.startswith("---"):
            return {}, text
        parts = text.split("---", 2)
        if len(parts) < 3:
            return {}, text
        meta = {}
        for line in parts[1].strip().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip('"').strip("'")
        return meta, parts[2].strip()

    def write_memory_file(self, name: str, mem_type: str, description: str, body: str):
        """Write a memory file with frontmatter"""
        slug = name.lower().replace(" ", "-").replace("/", "-")
        filename = f"{slug}.md"
        filepath = self.MEMORY_DIR / filename
        filepath.write_text(
            f"---\nname: {name}\ndescription: {description}\ntype: {mem_type}\n---\n\n{body}\n"
        )
        self._rebuild_index()
        return filepath

    def _rebuild_index(self):
        """Scan all the memory file and then rebuild the index in MEMORY.md"""
        lines = []
        for f in sorted(self.MEMORY_DIR.glob("*.md")):
            if f.name == "MEMORY.md":
                continue
            raw = f.read_text(encoding="utf-8")
            meta, body = self._parse_frontmatter(raw)
            name = meta.get("name" ,f.stem)
            description = meta.get("description",body.split("\n")[0][:80])
            lines.append(f"- [{name}]({f.name}) - {description}")
        self.MEMORY_INDEX.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")

    def read_memory_index(self) -> str:
        """Read the MEMORY.md(Inject into SYSTEM in every turn)"""
        if not self.MEMORY_INDEX.is_file():
            return ""
        text = self.MEMORY_INDEX.read_text(encoding="utf-8").strip()
        return text if text else ""

    def read_memory_file(self, filename: str)-> str | None:
        """Read single memory file"""
        path = self.MEMORY_DIR / filename
        if not path.is_file():
            return None
        return path.read_text(encoding="utf-8")

    def list_memory_files(self) -> list[dict]:
        """List all memory files and meta information"""
        result: list[dict] = []
        for f in sorted(self.MEMORY_DIR.glob("*.md")):
            if f.name == "MEMORY.md":
                continue
            raw = f.read_text(encoding="utf-8")
            meta, body = self._parse_frontmatter(raw)
            result.append({
                "filename": f.name,
                "name": meta.get("name", f.stem),
                "description": meta.get("description", ""),
                "type": meta.get("type", "user"),
                "body": body,
            })
        return result

    def select_relevant_memories(self, messages: list, max_items: int=5) -> list[str]:
        """Use LLM API to Select Relevant Memory"""
        files = self.list_memory_files()
        if not files:
            return []

        #Collect at most five relevant user's message
        recent_texts = []
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if content:
                    recent_texts.append(content)
            if len(recent_texts) >= 5:
                break

        recent = " ".join(reversed(recent_texts))
        if not recent.strip():
            return []

        #Build memory dictionary for LLM to select
        catalog_lines = []
        for i, f in enumerate(files):
            catalog_lines.append(f"{i}: {f['name']} - {f['description']}")
        catalog = "\n".join(catalog_lines)

        prompt = (
            "Given the recent conversation and the memory catalog below, "
            "select the indices of memories that are clearly relevant. "
            "Return ONLY a JSON array of integers, e.g. [0, 3]. "
            "If none are relevant, return [].\n\n"
            f"Recent conversation:\n{recent}\n\n"
            f"Memory catalog:\n{catalog}"
        )

        try:
            response = _create_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
            )
            text = (response.choices[0].message.content or "").strip()
            if not text:
                logger.warning("记忆选择API返回空内容，无法选择相关记忆")
                return []
            match = re.search(r'\[.*?\]', text, re.DOTALL)
            if match:
                indices = json.loads(match.group())
                selected = []
                for idx in indices:
                    if isinstance(idx, int) and 0 <= idx < len(files):
                        selected.append(files[idx]["filename"])
                        if len(selected) >= max_items:
                            break
                return selected
        except Exception:
            logger.error("调用API总结记忆出错")
            typer.echo(typer.style("调用API总结记忆出错", fg=typer.colors.RED, bold=True))
            pass
        return []

    def load_memories(self, messages: list) -> str:
        """Load memory content and inject into LLM's context"""
        selected_files = self.select_relevant_memories(messages)
        if not selected_files:
            return ""
        parts = ["<relevant_memories>"]
        for filename in selected_files:
            content = self.read_memory_file(filename)
            if content:
                parts.append(content)
        parts.append("</relevant_memories>")
        return "\n\n".join(parts)

    def extract_memories(self, messages: list):
        """Extract memory content from recent conversations"""
        dialogue_parts = []
        for msg in messages[-10:]:
            role = msg.get("role", "?")
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    str(item.get("text", "")) for item in content
                    if item.get("type") == "text"
                )
            if isinstance(content, str) and content.strip():
                dialogue_parts.append(f"{role}: {content}")
        dialogue = "\n".join(dialogue_parts)
        if not dialogue.strip():
            return

        existing = self.list_memory_files()
        existing_desc = "\n".join(f"- {m['name']}: {m['description']}" for m in existing) if existing else "(none)"

        prompt = (
            "Extract user preferences, constraints, or project facts from this dialogue.\n"
            "Return a JSON array. Each item: {name, type, description, body}.\n"
            "- name: short kebab-case identifier (e.g. 'user-preference-tabs')\n"
            "- type: one of 'user' (user preference), 'feedback' (guidance), "
            "'project' (project fact), 'reference' (external pointer)\n"
            "- description: one-line summary for index lookup\n"
            "- body: full detail in markdown\n"
            "If nothing new or already covered by existing memories, return [].\n\n"
            f"Existing memories:\n{existing_desc}\n\n"
            f"Dialogue:\n{dialogue}"
        )

        try:
            response = _create_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
            )
            text = (response.choices[0].message.content or "").strip()
            if not text:
                logger.warning("记忆提取API返回空内容，无法提取记忆")
                return
            match = re.search(r'\[.*\]', text, re.DOTALL)
            if not match:
                return
            items = json.loads(match.group())
            if not items:
                return
            count = 0
            for mem in items:
                name = mem.get("name", f"memory_{int(time.time())}")
                mem_type = mem.get("type", "user")
                desc = mem.get("description", "")
                body = mem.get("body", "")
                if desc and body:
                    self.write_memory_file(name, mem_type, desc, body)
                    count += 1
            typer.echo(typer.style(f"\n[Memory: extracted {count} new memories]", fg=typer.colors.GREEN, bold=True))

        except Exception:
            logger.error("调用API提取记忆出错")
            typer.echo(typer.style("调用API提取记忆出错", fg=typer.colors.RED, bold=True))
            pass

    def consolidate_memories(self):
        """Merge duplicate or expired memories. Trigger when the file count meets or exceeds the threshold."""
        files = self.list_memory_files()
        if len(files) < self.CONSOLIDATE_THRESHOLD:
            return

        catalog = "\n\n".join(
            f"## {f['filename']}\nname: {f['name']}\ndescription: {f['description']}\n{f['body']}"
            for f in files
        )

        prompt = (
            "Consolidate the following memory files. Rules:\n"
            "1. Merge duplicates into one\n"
            "2. Remove outdated/contradicted memories\n"
            "3. Keep the total under 30 memories\n"
            "4. Preserve important user preferences above all\n"
            "Return a JSON array. Each item: {name, type, description, body}.\n\n"
            f"{catalog}"
        )

        try:
            response = _create_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=3000,
            )
            text = (response.choices[0].message.content or "").strip()
            if not text:
                logger.warning("记忆整合API返回空内容，无法整合记忆")
                return
            match = re.search(r'\[.*\]', text, re.DOTALL)
            if not match:
                return
            items = json.loads(match.group())

            #Delete old files(Remain MEMORY.md)
            for f in self.MEMORY_DIR.glob("*.md"):
                if f.name != "MEMORY.md":
                    f.unlink()

            for mem in items:
                name = mem.get("name", f"memory_{int(time.time())}")
                mem_type = mem.get("type", "user")
                desc= mem.get("description", "")
                body = mem.get("body", "")
                if desc and body:
                    self.write_memory_file(name, mem_type, desc, body)

            typer.echo(typer.style(f"\n[Memory: consolidated {len(files)} → {len(items)} memories]", fg=typer.colors.GREEN, bold=True))

        except Exception:
            logger.error(f"调用API整合记忆文件失败")
            typer.echo(typer.style(f"调用API整合记忆文件失败", fg=typer.colors.RED, bold=True))
            pass

    def build_system(self)->str:
        index = self.read_memory_index()
        return (
            f"\n\n ## 可查看记忆: \n {index}\n "
            f"在接下来用户的消息里，你会看到相关的记忆内容，请遵守它们"
        ) if index else ""

MEMORY_SYSTEM = Memory()

