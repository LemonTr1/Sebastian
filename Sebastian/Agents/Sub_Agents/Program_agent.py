from agents import *
import typer
from Tools.File_Tools import ls_tool, create_file_with_content

from Interface.UserInfo import UserInfo
from cli import deepseek_model

program_agent = Agent[UserInfo](
    name = "Programmer",
    model=deepseek_model,
    instructions=(
        "你是一个擅长编写代码的助手，请严格遵守以下步骤：\n"
        "1.如果用户要求编写/修改/解释代码，但并没提及代码所在的目录和路径，则按你自己的逻辑正常回答用户。否则进入步骤2\n"
        "2.如果用户给出了代码所在的目录的路径，\n"
    ),
    model_settings=ModelSettings(
        temperature=0.2,
        max_tokens=1000
    ),
    tools=[ls_tool, create_file_with_content]
)