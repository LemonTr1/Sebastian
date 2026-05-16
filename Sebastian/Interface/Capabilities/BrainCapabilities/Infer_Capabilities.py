from Interface.Capabilities.BrainCapabilities.Capabilities import Capabilities
from agents import Runner, ModelSettings, Agent

from Interface.Exception.SecurityException import SecurityException
from models import deepseek_model
import re

#所有可能的恶意命令
DANGEROUS_PATTERNS = [
    r"rm\s+-rf\s+[/\\]",
    r"mkfs\.\w+",
    r":\(\)\{\s*:\|:\&\};:",
]

def security_guard(command: str) -> None:
    for p in DANGEROUS_PATTERNS:
        if re.search(p, command, re.I):
            raise SecurityException("高危操作被系统拦截")

async def infer_capabilities(command: str):
    #检查命令安全性
    security_guard(command)
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

        "=== CRITICAL PRIORITY RULE ===\n"
        "When a command involves BOTH code/content AND file system operations, "
        "File ALWAYS takes precedence over Code. The presence of a file path, "
        "file name, directory, or explicit save/read/create/delete action on a file "
        "AUTOMATICALLY makes it File, regardless of the content type.\n\n"

        "=== LABEL DEFINITIONS ===\n"
        "- File: File SYSTEM operations. Creating/reading/writing/deleting/moving/copying "
        "files or directories, compressing/decompressing, changing permissions, searching files. "
        "INCLUDES: saving code to a file, writing a script to disk, reading source code from a file, "
        "creating .py/.js/.md files. If a file path or file operation is mentioned, THIS IS ALWAYS THE ANSWER.\n"
        "- Code: PURE code logic WITHOUT file system involvement. Running scripts, debugging, "
        "algorithm design, math calculation, bash commands that don't touch files. "
        "ONLY choose this when NO file path, file name, or file operation is present.\n"
        "- Web: web search, download, real-time info query, URL access, API calls.\n"
        "- Git: git operations, GitHub repo management, clone/pull/push/commit/branch/status/diff.\n\n"

        "=== EXAMPLES ===\n"
        "Write a Python script and save it to app.py → File (saving to file path)\n"
        "Write a Python script to calculate primes → Code (no file path, pure logic)\n"
        "Create main.py → File (file creation)\n"
        "Read main.py → File (file reading)\n"
        "Edit the code in main.py → File (editing a file)\n"
        "Run the code → Code (execution, no file operation)\n"
        "Debug this function → Code (debugging logic, no file path)\n"
        "Download a file from web → Web\n"
        "Check git status → Git\n\n"

        "If none match, output exactly: None"
        )
    )
    result = await Runner.run(agent, input=command)
    context = result.final_output
    if context == "File":
        cap =  Capabilities.FILE_EXECUTE
    elif context == "Code":
        cap =  Capabilities.CODE_EXECUTE
    elif context == "Web":
        cap =  Capabilities.WEB_EXECUTE
    elif context == "Git":
        cap = Capabilities.GIT_EXECUTE
    else:
        raise PermissionError(f"Unexpected output from judger agent: {context}")

    #最后一根保险丝在最容易混淆的Code和File上
    if any(word in command for word in ["读取", "写入", "查看", "创建", "删除", "移动", "重命名", "复制", "查找", "压缩", "解压"]) and cap == Capabilities.CODE_EXECUTE:
        cap = Capabilities.FILE_EXECUTE

    return cap


