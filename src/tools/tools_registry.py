class ToolsRegistry:
    def __init__(self):
        self.hitl_tools: list[str] = []
        self.tools_map: dict[str, tuple] = {}
        self.agent_tools: dict[str, list[str]] = {}

    def register_tool(self, tool_name, tool_func, schema, hitl=False, for_agent=None):
        """注册工具，可指定归属Agent"""
        self.tools_map[tool_name] = (tool_func, schema)
        if hitl:
            self.hitl_tools.append(tool_name)
        if for_agent:
            self.agent_tools.setdefault(for_agent, []).append(tool_name)

    def get_tool(self, tool_name) -> tuple | None:
        """获取工具元(格式：<工具函数，工具schema>)"""
        return self.tools_map.get(tool_name, None)

    def is_hitl_tool(self, tool_name) -> bool:
        """判断是否为HITL工具"""
        return tool_name in self.hitl_tools

    def get_tools_for_agent(self, agent_name):
        """按Agent名获取 (tools_list, hitl_set)"""
        names = self.agent_tools.get(agent_name, [])
        tools = [self.tools_map[n] for n in names if n in self.tools_map]
        hitl = {n for n in names if n in self.hitl_tools}
        return tools, hitl

TOOLS_REGISTRY = ToolsRegistry()

def get_tools_registry() -> ToolsRegistry:
    return TOOLS_REGISTRY
