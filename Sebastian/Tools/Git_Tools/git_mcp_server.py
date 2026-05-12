from agents import function_tool, ModelSettings, Agent, Runner
from agents.mcp import MCPServerStdio
from models import deepseek_model
from pathlib import Path
import os
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['all_proxy'] = ''
from dotenv import load_dotenv
load_dotenv()

@function_tool
async def git_mcp_server(command: str):
    """
    这是一个通过MCP与本地运行的Git MCP Server交互的工具函数。它接受一个自然语言描述的Git操作命令，使用MCP调用本地的Git MCP Server执行相应的操作，并返回执行结果的摘要。
    Args:
        command: 自然语言的指令描述，要求准确，完整，简洁，清晰
    Returns:
        结构化字典，包括success, summary字段
    """
    home = Path.home()
    git_agent_workspace = os.path.join(home, "git_agent_workspace")
    if os.path.isdir(git_agent_workspace):
        os.makedirs(git_agent_workspace, exist_ok=True)
    try:
        async with MCPServerStdio(
            name="Git MCP Server",
            params={
                "command": "npx",
                "args": [
                    "-y",
                    "@cyanheads/git-mcp-server@latest"
                ],
                "env": {
                    "MCP_TRANSPORT_TYPE": "stdio",
                    "MCP_LOG_LEVEL": "error",
                    "GIT_BASE_DIR": git_agent_workspace,
                    "LOGS_DIR": f"{git_agent_workspace}/logs/git-mcp-server/",
                    "GIT_USERNAME": f"{str(os.getenv('GIT_USERNAME'))}",
                    "GIT_EMAIL": f"{str(os.getenv('GIT_EMAIL'))}",
                    "GIT_SIGN_COMMITS": "true"
                }
            }
        ) as server:
            agent = Agent(
                name="Git MCP Server",
                instructions="使用MCP服务完成指令，要求回答结果准确，完整，简洁，清晰",
                model=deepseek_model,
                mcp_servers=[server],
                model_settings=ModelSettings(
                    tool_choice="auto"
                )
            )
            result = await Runner.run(
                agent,
                input=command
            )
            return {
                "success": True,
                "summary": result.final_output
            }
    except Exception as e:
        return {
            "success": False,
            "summary": str(e)
        }