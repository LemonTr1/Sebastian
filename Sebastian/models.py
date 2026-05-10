import os
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['all_proxy'] = ''
from dotenv import load_dotenv
load_dotenv()
from openai import AsyncOpenAI #引入异步客户端
from agents import *

#创建指向 DeepSeek 的异步客户端（Agents SDK 底层基于 AsyncOpenAI）
client = AsyncOpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"), #从环境变量中获取
    base_url=os.getenv("DEEPSEEK_BASE_URL"),
)

#关闭追踪，DeepSeek不支持
set_tracing_disabled(True)

#将DeepSeek封装成Agents SDK可用的模型对象
deepseek_model = OpenAIChatCompletionsModel(
    model=str(os.getenv("DEEPSEEK_MODEL")),
    openai_client=client,
)