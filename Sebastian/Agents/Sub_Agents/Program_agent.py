from agents import *
import typer
from Tools.File_Tools import ls_tool, mkdir_tool

from Interface.UserInfo import UserInfo
from cli import deepseek_model

program_agent = Agent[UserInfo](
    name = "Programmer",
    model=deepseek_model,
    instructions=(
        "你是一个擅长编写代码的助手，请严格遵守以下步骤：\n"
        "1.如果用户要求编写/修改/解释代码，但并没提及代码所在的目录和路径，则按你自己的逻辑正常回答用户。否则进入步骤2\n"
        "2.如果用户给出了代码所在的目录的路径，必须先根据用户所给的路径作为字符串参数调用工具ls_tool，ls_tool返回结果后进入步骤3\n"
        "3.如果ls_tool返回值为None，直接回答用户不存在该路径，并提醒用户注意路径写法然后结束对话。否则进入步骤4\n"
        "4.请根据用户的请求作出以下判断\n"
        "  - 如果用户要求编写代码 -> 进入步骤5\n"
        "  - 如果用户要求修改/解释代码 -> 进入步骤6\n"
        "5.如果用户要求编写代码"
    ),
    model_settings=ModelSettings(
        temperature=0.2,
        max_tokens=1000
    ),
    tools=[ls_tool, mkdir_tool]
)