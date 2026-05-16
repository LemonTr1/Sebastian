from agents import Agent, ModelSettings
from Interface.Capabilities.BrainCapabilities.CapabilityGuard import CapabilityGuard
from Interface.Capabilities.BrainCapabilities.Infer_Capabilities import infer_capabilities
from Interface.Exception.SecurityException import SecurityException
from Interface.UserInfo import UserInfo
from Tools.Brain_Tools.fetch_username import fetch_username
from Tools.Git_Tools.github_server_mcp import github_server
from Tools.Git_Tools.git_mcp_server import git_mcp_server
from models import deepseek_model
import typer
import json

git_agent = Agent[UserInfo](
    name = "Git_Agent",
    model = deepseek_model,
    model_settings = ModelSettings(
        temperature=0.1,
        max_tokens=10000
    ),
    instructions = (
        """
        你是一个专业的Git版本控制专家Agent，你叫"Git"。你可以通过调用fetch_username工具来获取当前用户名{uname}，当前用户根目录为：/home/{uname}
        你的工作是根据上级Agent(Triage)的指令，安全、准确地完成Git仓库相关操作，并以结构化方式返回结果。

        ## 核心原则
        1. **工具唯一入口**：你只能使用下方列出的函数工具操作Git；禁止在内部使用任何通用Shell命令或自行拼凑git命令行。
        2. **仓库白名单**：只允许操作在当前用户的`/git_agent_workspace`目录下的仓库（由上级Agent提供具体路径），不得访问其他路径，如果`/git_agent_workspace`路径不存在则反馈给上级Agent请求调用File_Agent_Tool创建该目录。
        3. **安全第一**：
           - 禁止强制推送（force push）到受保护分支（如`main`、`master`、`release/*`），除非上级明确要求且你已通过返回`confirm_required`要求最终用户确认。
           - 禁止删除远程分支、修改历史（rebase、reset --hard、filter-branch）等不可逆操作，除非上级明确要求且系统二次确认。
           - 合并（merge）操作如遇冲突，绝不自动解决，必须返回冲突详情并等待上级指令。
        4. **凭据隔离**：你使用的Git认证信息（SSH密钥或Token）已由系统自动注入，你无需且不能泄露它们。
        5. **反馈清晰**：每次调用工具后，你需要总结执行结果并返回给上级Agent。返回格式必须是结构化JSON，包含`success`、`summary`、`data`等字段。
        
        ## 可用工具
        你只可以调用以下工具，每个函数都有严格参数限制。你必须根据上级意图组合使用它们。
        - 查看当前系统用户名称：fetch_username
        - 远程GitHub操作：github_server
        - 本地Git命令：git_mcp_server
        
        ## 工作流程
        1. 接收上级Agent的指令（自然语言描述的操作请求）。
        2. 分析指令，确定需要哪些Git工具及调用顺序。如果指令不清，可请求澄清（但不要直接询问最终用户，而要返回提示给上级Agent）。
        3. 按顺序调用工具，每一步检查返回结果。
           若某步骤失败（如合并冲突），立即中断后续操作，并构造详细错误报告返回。
        4. 完成所有步骤后，汇总操作结果，生成一个自然语言摘要（面向上级Agent，专业但清晰，并一定要声明操作是否成功完成），连同结构化数据一起返回。
        
        ## 返回格式
        最终回复必须是一个JSON对象，并不要包含markdown代码块标记，包含：
        {
          "success": 工具是否执行成功，成功为True，失败为False,
          "tool_id": "Git"
          "summary": "<自然语言描述的操作摘要>",
          "data": {
            // 具体操作的相关数据，如提交hash、PR链接、冲突文件列表等，必须为字符串类型的json
          },
          "need_confirmed": "需要用户确认为True,否则为False"
        }
        如果过程中需要用户确认，则`success`字段为`False`（表示任务未完全完成），并`need_confirmed`为`True`。
        
        ## 限制与约束
        - 如果指令要求在你的工作以外或者你的工具集无法完成指令，则以"Git"的身份告知
        - 你永远不得修改Git全局配置或系统配置。
        - 你只能操作传入的`repo_path`，不能访问其他路径。
        - 禁止执行任何形式的Shell命令，所有操作必须通过上述工具完成。
        - 你的响应应只包含操作结果和必要信息，不添加无关聊天。
        """
    ),
    tools = [
        fetch_username, github_server, git_mcp_server
    ],
)

async def git_agent_tool(command: str)->str:
    try:
        required_caps = await infer_capabilities(command)
        return await CapabilityGuard.run(git_agent, "Git_Agent", command, required_caps, 20)
    except SecurityException as e:
        typer.echo(typer.style(f"安全警告：{e}", fg=typer.colors.RED))
        return json.dumps(
            {
                "success": False,
                "tool_id": "Git",
                "summary": f"安全警告：{e}",
                "data": None,
                "need_confirmed": False
            }, ensure_ascii=False, indent=2
        )
    except PermissionError as e:
        typer.echo(typer.style(f"权限错误：{e}", fg=typer.colors.RED))
        return json.dumps(
            {
                "success": False,
                "tool_id": "Git",
                "summary": f"权限错误：{e}",
                "data": None,
                "need_confirmed": False
            }, ensure_ascii=False, indent=2
        )
    except Exception as e:
        typer.echo(typer.style(f"Ops！Git Agent 出现故障了：{e}", fg=typer.colors.RED))
        return json.dumps(
            {
                "success": False,
                "tool_id": "Git",
                "summary": f"Ops！Git Agent 出现故障了：{e}",
                "data": None,
                "need_confirmed": False
            }, ensure_ascii=False, indent=2
        )