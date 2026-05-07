from agents import *
from openai.types.responses import ResponseTextDeltaEvent

from cli import deepseek_model
from Agents.Sub_Agents.File_agent import file_agent
from Agents.Sub_Agents.Web_agent import web_agent
from Agents.Sub_Agents.Code_Agent import code_agent
from Agents.Sub_Agents.Git_Agent import git_agent
from Interface.UserInfo import UserInfo
from Tools.Web_Tools.correct_time_tool import get_current_datetime
import typer

brain_agent = Agent[UserInfo](
    name="Triage",
    model=deepseek_model,
    instructions=(
        """
        你是 Sebastian 的主控大脑，负责理解用户意图，调度底层专家 Agent 完成任务，并给出最终回答。
        
        ## 1. 路由边界（必须严格遵守）
        - 纯闲聊/打招呼/无实际操作需求的对话 -> 直接回复，禁止调用任何工具。
        - 关于Git的操作：仓库克隆,拉取,推送，/查看状态、日志、差异/分支管理（创建、切换、合并、删除/提交修改（暂存、提交、写提交信息)/处理冲突/创建 Pull Request/Merge Request(调用 GitHub/GitLab API)/代码审查（diff分析+评论)->交给Git_Agent_Tool
        - 编写代码/执行Bash命令/执行代码/运行脚本/进行数学计算 -> Code_Agent_Tool
        - 对文件系统对象的查看/创建/删除/移动/重命名/复制/查找/修改权限/压缩解压，以及对文件内容的读取/修改 -> File_Agent_Tool
        - 时间查询/公网实时信息搜索/网页内容抓取/网络资源下载 -> Web_Agent_Tool
        - 查询用户私有文档/本地知识库 -> Knowledge_Agent_Tool
        - 发送系统通知/消息推送 -> Notify_Agent_Tool
        （注意：绝对禁止跨界！比如禁止用 Web_Agent 查本地笔记，禁止用 Code_Agent 读文件内容）
        
        ## 2. 工作流
        - 拆解任务，按需调用工具。如果多个工具之间没有依赖关系（如同时搜两个网页、同时查文件和知识库），请务必并行调用。
        - 拿到工具结果后，由你进行提炼、对比、总结，必须用人类友好的自然语言输出，禁止直接把工具的原始返回结果（如 JSON、代码块、大段无格式文本）甩给用户。
        
        ## 3. 交互规范
        - 涉及高危操作（如批量删除、覆盖重要文件、执行不可逆脚本），你必须先用自然语言向用户解释你的具体执行计划，等用户明确同意后，再调用对应的工具。
        - （注：底层工具自身带有强制确认机制，但作为大脑，你应该主动承担前期的沟通与预警责任，避免发出无效的危险指令。）
        
        ## 4. 补充规则
        - 如果一个任务需要多个 Agent 协作（如文件重命名后提交 Git），你应该在单轮中顺序组合调用，并向用户解释每一步的用途。
        - 代码执行环境（Code_Agent_Tool）仅限于沙箱临时目录，禁止直接访问用户个人文件夹；文件持久化请结合 File Agent。
        - Git_Agent_Tool 的操作对象必须限定在已注册的仓库白名单内；不允许通过参数拼接执行任意 Git 命令。
        - 当你需要查询“是否已有相关文档/笔记”时，优先调用 Knowledge Agent；同时如需补充网络信息，可同步调用 Web Agent，并在最终回答中明确区分来源。
        - 对于不可逆操作（如 merge、rebase、强制覆盖），即使底层工具有确认，你也必须提前用自然语言告知用户影响范围（如会修改哪些分支历史、是否可能丢代码）。
        """
    ),
    model_settings=ModelSettings(
        temperature=0.2,
        max_tokens=30000
    ),
    tools=[
        get_current_datetime,
        file_agent.as_tool(
            tool_name="File_Agent_Tool",
            tool_description="负责对文件系统对象进行：查看/创建/删除/移动/重命名/复制/查找/修改权限/压缩解压操作，以及对文件内容的读取/修改"
        ),
        web_agent.as_tool(
            tool_name="Web_Agent_Tool",
            tool_description="负责网络搜索，网页内容获取，网络资源下载"
        ),
        code_agent.as_tool(
            tool_name="Code_Agent_Tool",
            tool_description="负责执行代码、运行脚本、安装软件和进行数学计算"
        ),
        git_agent.as_tool(
            tool_name="Git_Agent_Tool",
            tool_description="负责执行Git操作"
        )
    ]
)

async def chat():
    uname = typer.prompt("当前系统用户名(一定要准确否则会影响后续操作)")
    UserInfo.uname = uname
    typer.echo(typer.style("Hello.I'm Sebastian.What can I do for you? [Press 'quit' to exit]", fg=typer.colors.BLUE))
    history = []
    while True:
        question = typer.prompt(typer.style("[You]", fg=typer.colors.GREEN, bold=True))
        if question.lower() in ["quit", "exit"]:
            typer.echo(typer.style("Bye", fg=typer.colors.BLUE, bold=True))
            raise typer.Exit(code=0)
        history.append({"role":"user", "content":question})
        try:
            result = Runner.run_streamed(brain_agent, input=history, context=UserInfo(uname))
        except Exception as e:
            typer.echo(typer.style(f"Ops！机器人出现故障了：{e}", fg=typer.colors.RED, bold=True))
            raise typer.Exit(code=1)
        history = result.to_input_list()
        typer.echo(typer.style("[AI]: ", fg=typer.colors.BLUE, bold=True), nl=False)
        async for event in result.stream_events():
            if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                typer.echo(typer.style(event.data.delta, fg=typer.colors.BLUE), nl=False)
        typer.echo()
