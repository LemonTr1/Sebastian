from src.agent_runner import AgentRunner
from src.tools.web import get_current_time_str
from src.tools.tools_registry import get_tools_registry
from src.utils.user_info import get_username

uname = get_username()
current_time = get_current_time_str()

WEB_AGENT_INSTRUCTIONS = f"""
你是 Sebastian 的 **Web Agent**，负责网络搜索、网页抓取、文件下载、浏览器操作。
当前时间：{current_time}。用户名：{uname}。

## 工具选择
1. 搜索信息 → web_search
2. 提取网页正文 → web_extract
3. 下载文件 → download_file
4. 浏览器操作 → browser_* 系列

## 输出格式
{{
  "success": true,
  "operator": "Web",
  "tool_name": [],
  "summary": "操作摘要",
  "data": {{}},
  "need_confirmed": false
}}
"""

web_agent = AgentRunner.create_runner(
    name="Web_Agent",
    instructions=WEB_AGENT_INSTRUCTIONS,
    registry=get_tools_registry(),
)
