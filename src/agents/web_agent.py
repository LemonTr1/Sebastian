import os
from src.agent_runner import AgentRunner
from src.tools.web.search import web_search, WEB_SEARCH_SCHEMA
from src.tools.web.extract import web_extract, WEB_EXTRACT_SCHEMA
from src.tools.web.download import download_file, DOWNLOAD_FILE_SCHEMA
from src.tools.web.browser import (
    browser_launch, browser_info, browser_navigate, browser_click,
    browser_fill, browser_screenshot, browser_scroll, browser_wait,
    browser_js, browser_get_cookies, browser_set_cookies, browser_close,
    BROWSER_LAUNCH_SCHEMA, BROWSER_INFO_SCHEMA, BROWSER_NAVIGATE_SCHEMA,
    BROWSER_CLICK_SCHEMA, BROWSER_FILL_SCHEMA, BROWSER_SCREENSHOT_SCHEMA,
    BROWSER_SCROLL_SCHEMA, BROWSER_WAIT_SCHEMA, BROWSER_JS_SCHEMA,
    BROWSER_GET_COOKIES_SCHEMA, BROWSER_SET_COOKIES_SCHEMA, BROWSER_CLOSE_SCHEMA,
)
from src.tools.web import get_current_time_str

uname = os.getlogin()
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

_WEB_TOOLS = [
    (web_search, WEB_SEARCH_SCHEMA),
    (web_extract, WEB_EXTRACT_SCHEMA),
    (download_file, DOWNLOAD_FILE_SCHEMA),
    (browser_launch, BROWSER_LAUNCH_SCHEMA),
    (browser_info, BROWSER_INFO_SCHEMA),
    (browser_navigate, BROWSER_NAVIGATE_SCHEMA),
    (browser_click, BROWSER_CLICK_SCHEMA),
    (browser_fill, BROWSER_FILL_SCHEMA),
    (browser_screenshot, BROWSER_SCREENSHOT_SCHEMA),
    (browser_scroll, BROWSER_SCROLL_SCHEMA),
    (browser_wait, BROWSER_WAIT_SCHEMA),
    (browser_js, BROWSER_JS_SCHEMA),
    (browser_get_cookies, BROWSER_GET_COOKIES_SCHEMA),
    (browser_set_cookies, BROWSER_SET_COOKIES_SCHEMA),
    (browser_close, BROWSER_CLOSE_SCHEMA),
]

WEB_HITL_TOOLS = {"download_file"}

web_agent = AgentRunner.create_runner(
    name="Web_Agent",
    instructions=WEB_AGENT_INSTRUCTIONS,
    tools=_WEB_TOOLS,
    hitl_tools=WEB_HITL_TOOLS,
)
