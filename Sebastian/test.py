import asyncio
from agents import Agent, Runner, RunContextWrapper, AgentHooks


# 1. 定义钩子的行为
class MyHooks(AgentHooks):
    async def on_agent_end(self, context: RunContextWrapper, agent: Agent, result):
        # ✅ 在这里访问用量统计信息
        if result.usage:
            print(f"\n[📊 Token 用量 (来自 on_agent_end) for {agent.name}]")
            print(f"   - 输入 Tokens: {result.usage.input_tokens}")
            print(f"   - 输出 Tokens: {result.usage.output_tokens}")
            print(f"   - 总计 Tokens: {result.usage.total_tokens}")


# 2. 创建一个带有钩子的 Agent
my_agent = Agent(
    name="StreamingAssistant",
    instructions="你是一个语言助手,请简短回答。",
    hooks=MyHooks()  # 关键: 挂载钩子
)


async def main():
    # 3. 发起流式运行
    result = Runner.run_streamed(my_agent, "Hello, can you tell me a short story?")

    # 4. 消费流式事件,显示打字机效果
    async for event in result.stream_events():
        # ... 这里处理流式事件以实现实时展示 ...
        pass

    # 5. 等待流式输出展示完毕后，程序结束
    # 此时钩子 `on_agent_end` 已被自动调用并打印用量信息
    print("\n[✓] 流式输出结束。")


if __name__ == "__main__":
    asyncio.run(main())
