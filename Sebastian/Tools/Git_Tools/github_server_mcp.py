from agents import function_tool, ModelSettings, Agent, Runner
from agents.mcp import MCPServerStdio
from models import deepseek_model
import os
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['all_proxy'] = ''
from dotenv import load_dotenv
load_dotenv()

@function_tool
async def github_server(command: str):
    """
    这是一个通过MCP与本地运行的GitHub Server交互的工具函数。它接受一个自然语言描述的GitHub操作指令，使用MCP调用本地的GitHub Server执行相应的操作，并返回执行结果的摘要。
    Args:
        command: 自然语言的指令描述，要求准确，完整，简洁，清晰
    Returns:
        结构化字典，包括success, summary字段
    """
    try:
        token = os.getenv('GITHUB_TOKEN')
        async with MCPServerStdio(
            name="GitHub Local MCP",
            params={
                "command": "npx",
                "args": [
                    "-y",
                    "@modelcontextprotocol/server-github"
                ],
                "env": {
                    "GITHUB_PERSONAL_ACCESS_TOKEN": token
                }
            },
            cache_tools_list=True,
        ) as server:
            agent = Agent(
                name="Assistant",
                instructions="Use the MCP tools to execute the command.",
                model=deepseek_model,
                mcp_servers=[server],
                model_settings=ModelSettings(tool_choice="required"),
            )
            #跑子Agent
            result = await Runner.run(
                agent,
                input=command,
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

