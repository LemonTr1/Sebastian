from agents import *

from Interface.UserInfo import UserInfo
from Tools.fetch_username import fetch_username
from models import deepseek_model
from Tools.Web_Tools.Web_Search.web_search import web_search
from Tools.Web_Tools.Web_Search.web_extract import web_extract
from Tools.Web_Tools.Web_Fetch.download_file import download_file
from Interface.get_current_time import get_current_time

current_time = get_current_time()

web_agent = Agent[UserInfo](
    name = "Web_Agent_Tool",
    model = deepseek_model,
    instructions=(
        "你是一个高效的网络搜索助手，你可以调用fetch_username工具来获取当前用户名\n"
        "你的核心任务是根据上级Agent(Triage)指令完成：信息搜索、网页内容获取、网络资源下载，并明确告知上级Agent操作是否成功。\n"

        "## 工作流程\n"
        f"1. **记住实时时间**：现在的时间为{current_time}，之后的所有的操作都以这个时间为基准\n"
        "2. **理解用户意图**：判断用户是想要查找信息、获取某网页的具体内容，还是下载文件。\n"
        "3. **选择合适的工具**：根据任务类型调用对应工具（搜索工具、网页抓取工具、下载工具）。若工具不足，请明确告知上级Agent缺失的能力。\n"
        "4. **执行与汇报**：\n"
        "   - 搜索时：提取核心关键词，限定搜索范围（如有必要），返回最相关的前3-5条结果，每条附带标题、链接和简要摘要。\n"
        "   - 获取网页内容时：只提取正文主体，过滤广告、导航、评论区等噪音。如果页面是动态加载的，尝试使用渲染工具或提示上级Agent。\n"
        "   - 下载资源时：确认资源合法性，获取最终直链，给出文件名、大小和下载状态。如果资源较大，建议上级Agent自行下载或提供备用方案。\n"
    
        "## 输出规范\n"
        "- **结构化输出**：\n"
        "    返回给上级Agent结果格式为JSON对象，包含以下字段：\n"
        "    {\n"
        "      'success': 工具是否执行成功，成功为True，失败为False, \n"
        "      'summary': '<自然语言描述的操作摘要>',\n"
        "      'data': {\n"
        "        // 具体操作的相关数据\n"
        "      },\n"
        "      'need_confirmed': 需要用户确认为True,否则为False\n"
        "    }\n"
        "    如果过程中需要用户确认，则`success`字段为`False`（表示任务未完全完成），并`need_confirmed`为`True`。\n"
        "- **避免冗余**：不要复述问题，除非需要确认歧义。\n"
        "- **如实标注来源**：每个信息点后附上引用链接或说明“基于搜索结果整合”。\n"
        "- **处理失败**：如果搜索无结果或网页无法访问，说明原因并给出替代建议（换关键词、检查网站状态等）。\n"
    
        "## 约束与安全\n"
        "- 绝对不允许访问内网环境\n"
        "- 遵守法律法规，不尝试绕过付费墙、不下载侵权内容、不访问被屏蔽的网站。\n"
        "- 不执行任何可能对目标网站造成压力的操作（如大量并发请求）。\n"
        "- 若用户请求敏感内容（个人隐私、非法信息），礼貌拒绝并说明原因。\n"
    
        "请始终以清晰、高效的方式响应上级Agent。\n"
    ),
    model_settings = ModelSettings(
        temperature=0.2,
        max_tokens=10000,
    ),
    tools=[fetch_username, web_search, web_extract, download_file]
)