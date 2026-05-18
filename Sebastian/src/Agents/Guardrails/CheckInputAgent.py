from agents import Agent, ModelSettings
from src.Interfaces.UserInfo import UserInfo
from src.Models.models import deepseek_model
from src.Tools.Brain_Tools.fetch_username import fetch_username

check_input_agent = Agent[UserInfo](
    name="CheckInputAgent",
    model=deepseek_model,
    instructions=(
        """
        你的任务是检查用户输入内容是否合法，你可以通过调用fetch_username工具来获取当前用户名{uname}
        所有路径必须先规范化为绝对路径（解析 `~`、`..`、符号链接等），并验证前缀是否完全匹配 `/home/{uname}/`
        如果用户输入中出现下面其中一种情况，立即拒绝请求：
        - 涉及危险命令的Shell命令如：'rm -r /'等
        - 用户请求查看或修改`/home/{uname}`外的路径，如`/etc`，`/proc`等
        - 用户输入中涉及政治，个人隐私，密码信息等敏感内容
        """
    ),
    tools=[fetch_username],
    model_settings=ModelSettings(
        temperature=0.0,
        max_tokens=100
    )
)