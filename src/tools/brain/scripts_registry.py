from pathlib import Path
import json
from dataclasses import dataclass
import re
import subprocess
import os
import stat

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"

@dataclass
class ScriptMeta:
    name: str
    description: str
    parameters: str
    script_path: Path

class ScriptRegistry:
    def __init__(self, scripts_dir: Path):
        self.scripts_dir = scripts_dir
        self.scripts_map: dict[str, ScriptMeta] = {}
        self.load_all_scripts()

    def load_all_scripts(self):
        for path in sorted(self.scripts_dir.glob("*.sh")):
            head = self._parse_script_head(path.read_text())
            name = head.get("name", path.name[:-3])
            description = head.get("description", "(No Description)")
            parameters = head.get("parameters", "None")
            script_path = path
            self.scripts_map[name] = ScriptMeta(name=name, description=description, parameters=parameters, script_path=script_path)

    def _parse_script_head(self, content: str) -> dict:
        pattern = re.compile(
            r'^\s*:\s*"\s*$\n'  # 匹配 : " 开头行
            r'(.*?)'  # 非贪婪捕获内部内容
            r'^\s*"\s*$',  # 匹配 " 结尾行
            re.MULTILINE | re.DOTALL
        )

        match = pattern.search(content)
        if not match:
            return {}

        result = {}
        for line in match.group(1).strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            kv = re.match(r'^(\w+):\s*(.*?)\s*$', line)
            if kv:
                result[kv.group(1).lower()] = kv.group(2)

        return result

    def scripts_describe_available(self) -> str:
        if not self.scripts_map:
            return "(no scripts available)"
        lines = []
        for name in sorted(self.scripts_map):
            meta = self.scripts_map[name]
            lines.append(f"- {meta.name}: {meta.description} (Parameters: {meta.parameters})")
        return "\n".join(lines)

    #供Agent使用的工具接口
    def execute_script(self, script_name: str, parameters: list, timeout: int = 20) -> str:
        if parameters is None:
            parameters = []
        script_path = self.scripts_map[script_name].script_path

        # 检查并添加Agent执行权限
        if not os.access(script_path, os.X_OK):
            try:
                os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            except PermissionError:
                return json.dumps({
                    "success": False,
                    "error": "无法添加执行权限，请手动运行: chmod +x " + str(script_path)
                }, ensure_ascii=False)

        try:
            result = subprocess.run(
                ["bash", str(script_path)] + parameters,
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

SCRIPT_REGISTRY = ScriptRegistry(SCRIPTS_DIR)

SCRIPT_REGISTRY_SCHEMA = {
    "type": "function",
    "function": {
        "name": "execute_script",
        "description": "执行指定的脚本，并返回结果。",
        "parameters": {
            "type": "object",
            "properties": {
                "script_name": {
                    "type": "string",
                    "description": "要执行的脚本名称，必须精确匹配已注册的脚本名称",
                },
                "parameters": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "传递给脚本的参数列表，不需要传参则传递空数组",
                },
            },
            "required": ["script_name", "parameters"],
        },
    },
}

def get_script_registry():
    return SCRIPT_REGISTRY

