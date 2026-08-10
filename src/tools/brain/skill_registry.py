from dataclasses import dataclass
import json
import subprocess
import os
import stat
from pathlib import Path
import re
from src.tools.tools_registry import get_tools_registry

BASE_DIR = Path.home() / ".sebastian"

SKILLS_DIR = BASE_DIR / "skills"

@dataclass
class SkillManifest:
    name: str
    description: str
    path: Path

@dataclass
class SkillDocument:
    manifest: SkillManifest
    body: str

class SkillRegistry:
    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self.documents: dict[str, SkillDocument] = {}
        self._load_all()

    def _load_all(self)->None:
        if not self.skills_dir.is_dir():
            Path.mkdir(self.skills_dir, parents=True, exist_ok=True)

        for path in sorted(self.skills_dir.rglob("SKILL.md")):
            meta, body = self._parse_frontmatter(path.read_text())
            name = meta.get("name", path.parent.name)
            description = meta.get("description", "No description provided.")
            manifest = SkillManifest(name=name, description=description, path=path)
            self.documents[name] = SkillDocument(manifest=manifest, body=body.strip())

    def _parse_frontmatter(self, text: str)->tuple[dict, str]:
        match = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
        if not match:
            return {}, text

        #标题和描述信息
        meta = {}
        for line in match.group(1).strip().splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
        return meta, match.group(2)

    def describe_available(self)->str:
        if not self.documents:
            return "(no skills available)"
        lines = []
        for name in sorted(self.documents):
            manifest = self.documents[name].manifest
            lines.append(f"- {manifest.name}: {manifest.description}")
        return "\n".join(lines)

    # 供Agent调用的加载整个Skill的工具
    def load_full_text(self, name: str) -> str:
        document = self.documents.get(name)
        if not document:
            known = ", ".join(sorted(self.documents)) or "(none)"
            return f"Error: Unknown skill: '{name}'. Available skills: {known} "

        return (
            f"<skill name=\"{document.manifest.name}\">\n"
            f"{document.body}\n"
            "</skill>"
        )

    # 供Agent执行脚本的工具
    def run_script(self, script_path: str, parameters = None, timeout: int = 180, run_in_background: bool = False) -> str:
        if parameters is None:
            parameters = []

        if not Path(script_path).is_relative_to(SKILLS_DIR) or Path(script_path).parent.name != "scripts":
            return json.dumps({
                "success": False,
                "error": f"可执行脚本路径必须在 {SKILLS_DIR} 目录下，并且其父目录名必须为`scripts`"
            }, ensure_ascii=False)

        if not Path(script_path).is_file():
            return json.dumps({
                "success": False,
                "error": f"脚本不存在: {script_path}"
            }, ensure_ascii=False)

        # 检查并添加Agent执行权限
        if not os.access(script_path, os.X_OK):
            try:
                os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            except PermissionError:
                return json.dumps({
                    "success": False,
                    "error": "无法添加执行权限，告诉用户手动运行: chmod +x " + str(script_path)
                }, ensure_ascii=False)

        exec = "bash"
        if script_path.endswith(".py"):
            exec = "python3"

        try:
            result = subprocess.run(
                [exec, str(script_path)] + parameters,
                capture_output=True,
                text=True,
                check=True,
                timeout=timeout
            )

            return json.dumps({
                "success": True,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip()
            }, ensure_ascii=False)

        except subprocess.CalledProcessError as e:
            # 捕获 check=True 抛出的异常
            return json.dumps({
                "success": False,
                "error": e.stderr.strip() if e.stderr else f"脚本退出码: {e.returncode}"
            }, ensure_ascii=False)

        except subprocess.TimeoutExpired:
            return json.dumps({
                "success": False,
                "error": "Script execution timed out."
            }, ensure_ascii=False)

        except PermissionError:
            return json.dumps({
                "success": False,
                "error": "权限不足，无法执行脚本"
            }, ensure_ascii=False)

        except FileNotFoundError:
            return json.dumps({
                "success": False,
                "error": f"脚本文件不存在: {script_path}"
            }, ensure_ascii=False)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"执行脚本时发生错误: {str(e)}"
            }, ensure_ascii=False)

SKILL_REGISTRY = SkillRegistry(SKILLS_DIR)

def get_skill_registry():
    return SKILL_REGISTRY

SKILL_REGISTRY_SCHEMA = {
    "type": "function",
    "function": {
        "name": "load_skill",
        "description": "根据skill名称加载完整技能内容。",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "技能名称，必须精确匹配已注册的技能名称",
                },
            },
            "required": ["name"],
        },
    },
}

BASH_SCHEMA = {
    "type": "function",
    "function": {
        "name": "run_script",
        "description": "在宿主机执行技能系统内的脚本并返回结果。",
        "parameters": {
            "type": "object",
            "properties": {
                "script_path": {
                    "type": "string",
                    "description": "要执行的脚本，必须精确匹配已注册的脚本名称，必须使用绝对路径",
                },
                "parameters": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "可选，传递给脚本的参数列表，不需要传参时留空",
                },
                "run_in_background": {
                    "type": "boolean",
                    "description": "可选，是否在后台以异步方式运行，true表示以异步方式运行，默认为false"
                }
            },
            "required": ["script_path"],
        },
    },
}

#注册工具
get_tools_registry().register_tool("load_skill", SKILL_REGISTRY.load_full_text, SKILL_REGISTRY_SCHEMA, for_agent="Brain_Agent")
get_tools_registry().register_tool("run_script", SKILL_REGISTRY.run_script, BASH_SCHEMA, for_agent="Brain_Agent")