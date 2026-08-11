import json
from pathlib import Path
import typer
import re
from typing import List, Optional, NamedTuple
from src.logs.app_log import get_log
from src.agent_runner import AgentRunner
from src.tools.tools_registry import get_tools_registry
from src.utils.exceptions import SubAgentRuntimeException

logger = get_log()

#自定义子代理，如果此路径存在且非空优先从该路径提取
PRIVILEGE_DIR = Path.home() / ".sebastian" / ".agents"

#如果上述路径不存在则使用默认子代理
DEFAULT_DIR = Path(__file__).parent.parent.parent / "agents" / "subagents"

class SubAgentConfig(NamedTuple):
    name: Optional[str]
    description: Optional[str]
    tools: List[str]
    body: str

class SubAgentRegistry:
    def __init__(self):
        self.subagent_dir = PRIVILEGE_DIR
        self.subagent_meta: dict[str, dict] = {}
        self._load_all()

    def _parse_frontmatter(self, file_name: str, content: str) -> SubAgentConfig:
        """
        解析 subagent.md 文件，提取 YAML frontmatter 和提示词正文。

        Args:
            content: 文件完整文本内容

        Returns:
            SubAgentConfig: name, description, tools, body
        """
        content = content.lstrip("\ufeff")

        pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
        match = re.match(pattern, content, re.DOTALL)
        if not match:
            import warnings
            warnings.warn(f"{file_name}.md 文件缺少 YAML frontmatter或格式不正确，加载SubAgent信息失败。")
            logger.error(f"{file_name}.md 文件缺少 YAML frontmatter或格式不正确，加载SubAgent信息失败。")
            return SubAgentConfig(name=None, description=None, tools=[], body=content)

        frontmatter_text, body = match.group(1), match.group(2).strip()
        name: Optional[str] = None
        description: Optional[str] = None
        tools: List[str] = []

        # 逐行解析 frontmatter（只支持 key: value 单层结构）
        for line in frontmatter_text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue  # 跳过空行和注释

            if ":" not in line:
                continue  # 跳过不符合 key: value 的行

            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()

            if key == "name":
                name = value
            elif key == "description":
                description = value
            elif key == "tools":
                # 核心：用正则 \s*,\s* 分割，允许任意数量空白（包括0个）
                if value:
                    tools = [t.strip() for t in re.split(r"\s*,\s*", value) if t.strip()]

        return SubAgentConfig(name, description, tools, body)


    def _load_all(self):
        """
            从md文件中提取出子代理的元信息
            self.subagent_meta = {
                "subagent_name1": {
                    "description": str, "子代理描述",
                    "tools": list, 子代理可用工具集合,
                    "body": str, "子代理的system prompt"
                },
                "subagent_name2": {
                    ...
                }
            }
        """
        if not self.subagent_dir.is_dir():
            self.subagent_dir.mkdir(parents=True, exist_ok=True)

        if not list(self.subagent_dir.glob("*.md")):
            self.subagent_dir = DEFAULT_DIR

        for path in self.subagent_dir.glob("*.md"):
            with path.open("r", encoding="utf-8") as f:
                content = f.read()
                meta = self._parse_frontmatter(f.name, content)
                if meta.name is not None and meta.description is not None:
                    self.subagent_meta[meta.name] = {
                        "description": meta.description,
                        "tools": meta.tools,
                        "body": meta.body,
                    }

        if self.subagent_meta == {} and self.subagent_dir == PRIVILEGE_DIR:
            typer.echo(typer.style(f"\n> [Warn]检测到{str(PRIVILEGE_DIR)}中无有效SubAgent信息，已切换至默认",fg=typer.colors.YELLOW))
            logger.warning(f"检测到{str(PRIVILEGE_DIR)}中无有效SubAgent信息，已切换至默认")
            self.subagent_dir = DEFAULT_DIR

            for path in self.subagent_dir.glob("*.md"):
                with path.open("r", encoding="utf-8") as f:
                    content = f.read()
                    meta = self._parse_frontmatter(f.name, content)
                    if meta.name is not None and meta.description is not None:
                        self.subagent_meta[meta.name] = {
                            "description": meta.description,
                            "tools": meta.tools,
                            "body": meta.body,
                        }

    def describe_available(self) -> str:
        if not self.subagent_meta:
            return "(no subagents available)"
        lines = []
        for name in sorted(self.subagent_meta):
            description = self.subagent_meta[name].get("description", "No description provided.")
            tools = self.subagent_meta[name].get("tools", [])
            lines.append(f"- {name}: {description} (可用工具: {', '.join(tools) if tools else 'None'})")
        return "\n".join(lines)

    def agent(self, agent_name: str, task: str):
        """主Agent用于调度子Agent的工具"""
        try:
            #先给子Agent动态注册工具
            for tool in self.subagent_meta[agent_name].get("tools", []):
                tool = tool.lower()
                #绝不允许子Agent可以嵌套调用子Agent
                if tool == "agent": continue
                need_hitl = True if tool in ["bash", "edit", "write"] else False
                if tool in get_tools_registry().tools_map:
                    get_tools_registry().register_tool(
                        tool,
                        get_tools_registry().tools_map[tool][0],
                        get_tools_registry().tools_map[tool][1],
                        hitl=need_hitl ,for_agent=agent_name
                    )

            #然后创建子Agent
            sub_agent = AgentRunner.create_runner(
                name=agent_name,
                instructions=self.subagent_meta[agent_name].get("body", "You are a helpful assistant.Finish the task user provided"),
                registry=get_tools_registry()
            )

            #最后运行子Agent
            result = sub_agent.run(task)
            return json.dumps({
                "success": True,
                "summary": result
            }, ensure_ascii=False)
        except SubAgentRuntimeException as e:
            logger.error(f"{agent_name}运行时出错：{str(e)}")
            return json.dumps({
                "success": False,
                "error": f"{agent_name}运行时出错：{str(e)}"
            }, ensure_ascii=False)
        except Exception as e:
            logger.error(f"{agent_name}运行时出现未知错误：{str(e)}")
            return json.dumps({
                "success": False,
                "error": f"{agent_name}运行时出现未知错误：{str(e)}"
            }, ensure_ascii=False)


SUB_AGENT_REGISTRY = SubAgentRegistry()

AGENT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "agent",
        "description": "运行指定的子Agent以完成用户任务。",
        "parameters": {
            "type": "object",
            "properties": {
                "agent_name": {"type": "string", "description": "子Agent的名称"},
                "task": {"type": "string", "description": "以自然语言描述的任务"},
            },
            "required": ["agent_name", "task"],
        },
    },
}

get_tools_registry().register_tool("agent", SUB_AGENT_REGISTRY.agent, AGENT_SCHEMA, hitl=True, for_agent="Brain_Agent")

def get_sub_agent_registry():
    return SUB_AGENT_REGISTRY



