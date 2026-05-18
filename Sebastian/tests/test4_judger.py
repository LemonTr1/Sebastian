import asyncio

from agents import Runner, ModelSettings, Agent

from src.Models.models import deepseek_model

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
            "- Web: web search, download, real-time info query, URL access, API calls.\n"
            "- Git: git operations, GitHub repo management, clone/pull/push/commit/branch/status/diff.\n\n"
        
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
            "Check git status → Git\n\n"
        
            "If none match, output exactly: None"
        )
    )

async def main():
    while True:
        question = input("请输入：")
        result = await Runner.run(agent, input=question)
        print(result.final_output)

if __name__ == "__main__":
    asyncio.run(main())