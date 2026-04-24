#第一步永远先禁用代理
import os
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['all_proxy'] = ''
#从.env中加载配置信息
from dotenv import load_dotenv
load_dotenv(override=True)
from openai import AsyncOpenAI
from agents import Agent, Runner, OpenAIChatCompletionsModel, set_tracing_disabled
# 1. 创建指向 DeepSeek 的异步客户端（Agents SDK 底层基于 AsyncOpenAI）
client = AsyncOpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",  # 注意去掉尾部空格
)

# 2. 禁用 OpenAI 原生 Tracing（DeepSeek 不支持）
set_tracing_disabled(True)

# 3. 将 DeepSeek 包装为 Agents SDK 可用的模型对象
#    必须使用 OpenAIChatCompletionsModel，因为 DeepSeek 只兼容 Chat Completions API
deepseek_model = OpenAIChatCompletionsModel(
    model="deepseek-chat",
    openai_client=client,
)

# 4. 定义 Agent（instructions 相当于 system prompt）
agent = Agent(
    name="Assistant",
    instructions="You are a helpful assistant",
    model=deepseek_model,
)

# 5. 同步运行（对应原代码的 stream=False）
result = Runner.run_sync(agent, "Hello")
print(result.final_output)
