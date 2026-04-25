from agents import *
from test import deepseek_model
from Interface.UserInfo import UserInfo

chat_agent = Agent[UserInfo](
    name="Chatter",
    instructions=(
        "你是一个负责聊天和查询的助手。你的核心特点是：友善耐心地回答用户的每一个问题。\n"
    ),
    model=deepseek_model,
    model_settings=ModelSettings(
        temperature=0.8,
        max_tokens=1000
    )
)
