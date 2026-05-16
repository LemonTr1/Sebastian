from Interface.Capabilities.Capabilities import Capabilities
from agents import Runner, ModelSettings, Agent
from models import deepseek_model

#LLM对英文语境更敏感

async def infer_capabilities(command: str):
    agent = Agent(
        name="Judger",
        model_settings=ModelSettings(
            temperature=0.0,
        ),
        model=deepseek_model,
        instructions=(
            "You are an intent classifier. Your task is to classify the user's command "
            "into exactly one of the following labels. Output ONLY the label text, "
            "no quotes, no explanations, no markdown, no punctuation.\n\n"
            "Labels:\n"
            "- File: file system operations (read/write/delete/move/copy/compress/search)\n"
            "- Code: code writing, execution, math, bash commands\n"
            "- Web: web search, download, real-time info, URL access\n"
            "- Git: git operations, GitHub repo management, clone/pull/push/commit/branch\n\n"
            "If none match, output exactly: None\n"
            "Output format: single word, uppercase first letter."
        )
    )
    result = await Runner.run(agent, input=command)
    context = result.final_output.lower()
    if "file" in context:
        return Capabilities.FILE_EXECUTE
    elif "code" in context:
        return Capabilities.CODE_EXECUTE
    elif "web" in context:
        return Capabilities.WEB_EXECUTE
    elif "git" in context:
        return Capabilities.GIT_EXECUTE
    else:
        raise PermissionError(f"Unexpected output from judger agent: {context}")


