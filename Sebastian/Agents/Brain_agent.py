from agents import *
from cli import deepseek_model
from Agents.Sub_Agents.Chat_agent import chat_agent
from Agents.Sub_Agents.File_agent import file_agent
from Agents.Sub_Agents.Program_agent import program_agent
from Interface.UserInfo import UserInfo
import typer

brain_agent = Agent[UserInfo](
    name="Triage",
    model=deepseek_model,
    instructions=(
        "你是负责调度任务的。请记住你服务的用户名为{context.uname}，用户的管理员密码为{context.password}，你只需要分析用户意图，将任务分给合适的专家\n"
        "- 用户和你闲聊/打招呼/咨询问题 -> 交给Chatter\n"
        "- 用户请求在某个目录下编写/修改/解释/查看代码或文本，其中文本语言包括英语/简体中文/繁体中文/日语/俄语/法语，编程语言包括C/C++/Python/Shell/JavaScript等-> 交给Programmer\n"
        "- 用户请求进行有关文件操作，如文件操作：创建/删除/移动/重命名/复制/查找/修改权限/压缩解压 -> 交给FileManager\n"
        "绝对禁止直接回答用户问题，只能做路由判断"
    ),
    model_settings=ModelSettings(
        temperature=0.2,
        max_tokens=1000
    ),
    handoffs=[chat_agent, file_agent, program_agent]
)

def chat():
    uname = typer.prompt("您的姓名是(当前系统的用户名)")
    password = typer.prompt("您的root密码是[有些操作需要您的sudo权限]",hide_input=True)
    typer.echo("Hello.I'm Sebastian.What can I do for you? [Press 'quit' to exit]")
    history = []
    while True:
        question = typer.prompt(typer.style("[You]", fg=typer.colors.GREEN, bold=True))
        if question.lower() in ["quit", "exit"]:
            typer.echo(typer.style("Bye", fg=typer.colors.BLUE, bold=True))
            raise typer.Exit(code=0)
        history.append({"role":"user", "content":question})
        typer.echo(typer.style("[AI]: ", fg=typer.colors.BLUE, bold=True), nl=False)
        try:
            result = Runner.run_sync(brain_agent, input=history, context=UserInfo(uname, password))
            typer.echo(typer.style(f"\n[DEBUG]最后执行的Agent: {result.last_agent.name}\n", fg=typer.colors.YELLOW),
                       nl=False)
        except Exception as e:
            typer.echo(typer.style("This does not align with my aesthetic", fg=typer.colors.RED, bold=True))
            raise typer.Exit(code=1)
        history = result.to_input_list()
        typer.echo(typer.style(result.final_output, fg=typer.colors.BLUE))
