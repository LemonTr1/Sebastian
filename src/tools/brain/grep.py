import json
import re
from src.security.path_safety import resolve_safe_path
from src.utils.exceptions import SecurityException
from src.tools.tools_registry import get_tools_registry
import subprocess
from pathlib import Path

WORKDIR = Path.home()
MAX_RESULTS = 200      # 最大匹配行数
MAX_LINE_LEN = 300     # 单行截断长度
TIMEOUT = 30           # 搜索超时（秒）

def grep(pattern: str, path: str, case_sensitive: bool = True) -> str:
    try:
        search_path = resolve_safe_path(path)
    except SecurityException as e:
        return json.dumps({
            "success": False,
            "summary": str(e),
            "matches": []
        }, ensure_ascii=False)

    # 构建grep命令
    cmd = ["grep", "-rHn", "-E"]  # -r=recursive, -n=line numbers, -E=extended regex, -H=Since we want to show the filename even if there's only one file
    if not case_sensitive:
        cmd.append("-i")
    cmd.append("-m")
    cmd.append(str(MAX_RESULTS))
    cmd.append(pattern)
    cmd.append(str(search_path))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            cwd=WORKDIR
        )

        # 检查退出码：0=有匹配, 1=无匹配, 2+=出错（如选项错误、文件不存在）
        if result.returncode not in (0, 1):
            return json.dumps({
                "success": False,
                "summary": f"grep 执行出错 (rc={result.returncode}): {result.stderr.strip() or 'unknown error'}",
                "matches": []
            }, ensure_ascii=False)

        if result.returncode == 1:
            return json.dumps({
                "success": True,
                "summary": f"No matches found for pattern: {pattern}",
                "matches": []
            }, ensure_ascii=False)

    except subprocess.TimeoutExpired:
        return json.dumps({
            "success": False,
            "summary": f"Search timed out after {TIMEOUT}s. Use a more specific pattern or narrower path.",
            "matches": []
        }, ensure_ascii=False)
    except FileNotFoundError:
        return json.dumps({
            "success": False,
            "summary": "`grep` command not found. Please install grep.",
            "matches": []
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "matches": []
        }, ensure_ascii=False)

    # 解析grep结果: "[file_path] : [line_number:matched_text]"
    matches = []
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        # 非贪婪匹配：路径(.+?) + 行号(:数字:) + 内容(.*)
        # 行号必须是数字，这是区分"路径中的冒号"与"分隔冒号"的关键
        m = re.match(r'^(.+?):(\d+):(.*)$', line)
        if not m:
            continue
        file_path, line_num, text = m.group(1), m.group(2), m.group(3)
        # Strip workspace prefix for cleaner output
        rel_path = file_path
        if rel_path.startswith(str(WORKDIR)):
            rel_path = rel_path[len(str(WORKDIR)):].lstrip("/")
        matches.append({
            "file": rel_path,
            "line": int(line_num),
            "text": text[:MAX_LINE_LEN]
        })

    if not matches:
        return json.dumps({
            "success": True,
            "summary": f"No matches found for pattern: {pattern}",
            "matches": []
        }, ensure_ascii=False)

    summary = f"Found {len(matches)} match(es)"
    if len(matches) >= MAX_RESULTS:
        summary += f" (showing first {MAX_RESULTS}, refine your pattern for more precise results)"

    return json.dumps({
        "success": True,
        "summary": summary,
        "matches": matches
    }, ensure_ascii=False)

GREP_SCHEMA = {
    "type": "function",
    "function": {
        "name": "grep",
        "description": "Search file contents for a regex pattern. Returns file paths, line numbers, and matched text.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "模式匹配串"},
                "path": {"type": "string", "description": "查找路径，可以为文件或目录，必须以绝对路径表示"},
                "case_sensitive": {"type": "boolean", "description": "是否开启大小写敏感，true表示开启，false表示不敏感，默认true", "default": True}
            },
            "required": ["pattern", "path"]
        }
    }
}

#注册工具
get_tools_registry().register_tool("grep", grep, GREP_SCHEMA, for_agent="Brain_Agent")
