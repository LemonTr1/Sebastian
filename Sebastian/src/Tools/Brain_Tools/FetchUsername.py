from agents import function_tool, RunContextWrapper
from src.Interfaces.UserInfo import UserInfo

@function_tool
async def fetch_username(wrapper: RunContextWrapper[UserInfo]) -> str:
    """
    获取当前系统的用户名
    """
    return f"当前用户名为：{wrapper.context.uname}"