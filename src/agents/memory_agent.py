from src.agent_runner import AgentRunner
from src.tools.memory.memory_ops import (
    memory_store, memory_query, memory_list_collections, memory_delete_collection,
    MEMORY_STORE_SCHEMA, MEMORY_QUERY_SCHEMA, MEMORY_LIST_SCHEMA, MEMORY_DELETE_SCHEMA,
)

MEMORY_AGENT_INSTRUCTIONS = """
你是 Sebastian 的 **Memory Agent**，负责基于 ChromaDB 的知识库管理。

## 工具
- memory_store：存储文本到集合
- memory_query：语义检索
- memory_list_collections：列出集合
- memory_delete_collection：删除整个集合（不可逆，须先确认）

## 安全
- 禁止存储密码、密钥、Token等敏感信息
- 删除集合前须确认

## 输出格式
{
  "success": true,
  "operator": "Memory",
  "tool_name": [],
  "summary": "操作摘要",
  "data": {},
  "need_confirmed": false
}
"""

memory_agent = AgentRunner.create_runner(
    name="Memory_Agent",
    instructions=MEMORY_AGENT_INSTRUCTIONS,
    tools=[
        (memory_store, MEMORY_STORE_SCHEMA),
        (memory_query, MEMORY_QUERY_SCHEMA),
        (memory_list_collections, MEMORY_LIST_SCHEMA),
        (memory_delete_collection, MEMORY_DELETE_SCHEMA),
    ],
)
