"""CLI命令行入口"""
#禁用代理
import os
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['all_proxy'] = ''
#将.env配置加载到环境变量中
from dotenv import load_dotenv
load_dotenv(override=True)
from openai import AsyncOpenAI #引入异步客户端
from agents import *

import typer
from Agents import Brain_agent

#创建指向 DeepSeek 的异步客户端（Agents SDK 底层基于 AsyncOpenAI）
client = AsyncOpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"), #从环境变量中获取
    base_url=os.getenv("DEEPSEEK_BASE_URL"),
)

#关闭追踪，DeepSeek不支持
set_tracing_disabled(True)

#将DeepSeek封装成Agents SDK可用的模型对象
deepseek_model = OpenAIChatCompletionsModel(
    model="deepseek-chat",
    openai_client=client,
)

app = typer.Typer(no_args_is_help=False ,help="AutomaticTaskAssistant")

@app.callback(invoke_without_command=True)
def setup(version: bool = typer.Option(False, "--version", "-v", help="Show version and exit")):
    if version:
        typer.echo("Automatic Task Assistant V 0.1")
        raise typer.Exit(code=0)
    else:
        Brain_agent.chat()

if __name__ == "__main__":
    app()
