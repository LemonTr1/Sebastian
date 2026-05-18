import asyncio
from dataclasses import dataclass

from agents import Agent, RunContextWrapper, Runner, function_tool

from src.Models.models import deepseek_model


@dataclass
class UserInfo:
    name: str
    uid: int

@function_tool
async def fetch_user_age(wrapper: RunContextWrapper[UserInfo]) -> str:
    """Fetch the age of the user. Call this function to get user's age information."""
    return f"The user {wrapper.context.name} is 47 years old"

async def main():
    user_info = UserInfo(name="John", uid=123)

    agent = Agent[UserInfo](
        name="Assistant",
        model=deepseek_model,
        tools=[fetch_user_age],
    )

    result = await Runner.run(
        starting_agent=agent,
        input="What is the age of the user?",
        context=user_info,
    )

    print(result.final_output)
    # The user John is 47 years old.

if __name__ == "__main__":
    asyncio.run(main())