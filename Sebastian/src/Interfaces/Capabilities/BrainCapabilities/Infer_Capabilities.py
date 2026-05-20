from src.Interfaces.Capabilities.BrainCapabilities.Capabilities import Capabilities
from agents import Runner, ModelSettings, Agent
from src.Interfaces.Exception.SecurityException import SecurityException
from src.Models.models import deepseek_model
import re

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
        "use this order of precedence:\n"
        "1. EXECUTE/RUN/CALL EXCEPTION: If the PRIMARY VERB is execute, run, call, invoke, "
        "perform, or their Chinese equivalents (执行/运行/调用/启动), and the target is an "
        "EXISTING code file, script, project file, or program → classify as Code. "
        "The file is merely the CARRIER of the code; the real intent is execution, "
        "NOT file management.\n"
        "2. FILE MANAGEMENT: If the operation involves creating, reading (for inspection/copying), "
        "writing, saving, editing, deleting, moving, copying, compressing, decompressing, "
        "changing permissions, or searching files/directories → classify as File. "
        "INCLUDES: saving code to a file, writing a script to disk, creating .py/.js/.md files, "
        "reading source code from a file for modification. If the intent is to MANIPULATE the file "
        "itself, THIS IS ALWAYS THE ANSWER.\n\n"

        "=== LABEL DEFINITIONS ===\n"
        "- File: File SYSTEM MANAGEMENT. Creating/reading-for-copying/writing/deleting/moving/copying "
        "files or directories, compressing/decompressing, changing permissions, searching files. "
        "INCLUDES: saving code to a file, writing a script to disk, reading source code for "
        "modification, creating .py/.js/.md files. ONLY when the file ITSELF is the target of "
        "management, not when it is merely being executed.\n"
        "- Code: PURE code logic OR EXECUTION of existing code. Running scripts, executing code files, "
        "debugging, algorithm design, math calculation, bash commands that don't touch files, "
        "calling/invoking existing programs or scripts. INCLUDES: 'execute this code file', "
        "'run the project file', 'perform this script', 'call main.py'.\n"
        "- Web: web search, download, real-time info query, URL access, API calls, use Network Analysis and Security Scanning Tools and Digital Footprint and Open Source Intelligence (OSINT) Gathering Tools in the terminal.\n"

        "=== EXAMPLES ===\n"
        "执行这个代码文件 → Code (primary intent is execution, file is only the carrier)\n"
        "执行这个项目文件 → Code (running the project, not managing its files)\n"
        "运行 app.py → Code (executing an existing script)\n"
        "调用 test.py → Code (invoking existing code)\n"
        "Write a Python script and save it to app.py → File (creating/writing file)\n"
        "Write a Python script to calculate primes → Code (no file path, pure logic)\n"
        "Create main.py → File (file creation)\n"
        "Read main.py → File (reading file content for inspection)\n"
        "Edit the code in main.py → File (editing a file)\n"
        "Run the code → Code (execution, no file operation)\n"
        "Debug this function → Code (debugging logic, no file path)\n"
        "Download a file from web → Web\n"
        "在终端执行xxx命令，我要查xxx邮箱注册过的网站 -> Web (OSINT)\n"
        "在终端执行nmap命令，我要查xxx暴露的端口 -> Web(Network Analysis and Security Scanning)"
        "在终端使用tshark命令进行网络抓包 -> Web(Network Analysis and Security Scanning)"

        "If none match, output exactly: None"
        )
    )

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
    try:
        result = await Runner.run(agent, input=command)
    except SecurityException as e:
        raise SecurityException("Judger Agent出现故障，鉴权失败，指令无法下发")
    context = result.final_output
    if context == "File":
        cap =  Capabilities.FILE_EXECUTE
    elif context == "Code":
        cap =  Capabilities.CODE_EXECUTE
    elif context == "Web":
        cap =  Capabilities.WEB_EXECUTE
    else:
        raise PermissionError(f"Unexpected output from judger agent: {context}")

    #最后一层代码层面约束作为保险丝
    if any(word in command for word in ["读取", "写入", "查看", "创建", "删除", "移动", "重命名", "复制", "查找", "压缩", "解压"]) and cap == Capabilities.CODE_EXECUTE:
        cap = Capabilities.FILE_EXECUTE

    if any(word in command for word in ["执行", "运行", "execute"]) and cap == Capabilities.FILE_EXECUTE:
        cap = Capabilities.CODE_EXECUTE

    return cap


