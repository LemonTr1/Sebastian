import os
import re
import json
from pathlib import Path
import typer
from src.security.path_safety import resolve_safe_path
from src.utils.exceptions import SecurityException
from src.agents.file_agent import file_agent
from src.agents.code_agent import code_agent
from src.agents.web_agent import web_agent
from src.agents.memory_agent import memory_agent

HOME = str(Path.home())

_DISALLOWED_DIR = [
    os.path.join(HOME, "Desktop"),
    os.path.join(HOME, "桌面"),
    os.path.join(HOME, ".ssh"),
    os.path.join(HOME, ".gnupg"),
    os.path.join(HOME, ".aws"),
    os.path.join(HOME, ".docker"),
    os.path.join(HOME, ".kube"),
    os.path.join(HOME, ".config"),
    os.path.join(HOME, ".local"),
    os.path.join(HOME, ".cache"),
    os.path.join(HOME, ".mozilla"),
    os.path.join(HOME, ".thunderbird"),
]

_URL_PATTERN = re.compile(r'https?://\S+', re.IGNORECASE)

_QUOTED_PATTERN = re.compile(
    r'(?s)'
    r'```(?:.|\n)*?```'
    r'|\'\'\'(?:.|\n)*?\'\'\''
    r'|"""(?:.|\n)*?"""'
    r'|"(?:\\.|[^"\\])*"'
    r'|\'(?:\\.|[^\'\\])*\''
    r'|`(?:[^`\\]|\\.)*`',
    re.IGNORECASE,
)

_COMMENT_PATTERN = re.compile(
    r'(?s)'
    r'/\*.*?\*/'
    r'|<!--.*?-->'
    r'|#[^\n]*'
    r'|//[^\n]*',
    re.IGNORECASE,
)


def _strip_quoted_content(text: str) -> str:
    text = _QUOTED_PATTERN.sub('', text)
    return _COMMENT_PATTERN.sub('', text)


def _filter_paths(command: str, only_path: str, home: str = HOME) -> str | None:
    errors = []
    only_path = only_path.strip()
    if only_path in ("''", '""', '``', ''):
        only_path = ""
    if only_path:
        if not re.match(r'^https?://', only_path):
            np = only_path.strip()
            if np.startswith("~"):
                errors.append(f"only_path使用了'~'简写，请替换为绝对路径: {np}")
            elif ".." in np:
                errors.append(f"only_path包含'..': {np}")
            elif not np.startswith("/"):
                errors.append(f"only_path不是绝对路径: {np}")
            elif not np.startswith(home + "/"):
                errors.append(f"only_path不在用户根目录下: {np}")
    clean = _URL_PATTERN.sub("", command)
    clean = _strip_quoted_content(clean)
    path_pattern = re.compile(r'(/\S*/\S+)')
    for m in path_pattern.finditer(clean):
        p = m.group(1).rstrip(",.;:!?，。；：！？)")
        if not p.startswith(home + "/"):
            errors.append(f"command中路径不在用户根目录下: {p}")
    tilde_pattern = re.compile(r'(~/\S+)')
    for m in tilde_pattern.finditer(clean):
        errors.append(f"command中使用了'~'简写: {m.group(1)}")
    dotdot_pattern = re.compile(r'(?:[^\w/]|^)(\.\./\S+)')
    for m in dotdot_pattern.finditer(clean):
        errors.append(f"command中使用了'..': {m.group(1)}")
    if errors:
        return json.dumps(
            {
                "success": False,
                "tool_id": None,
                "summary": "路径安全校验失败：" + "；".join(errors),
                "data": None,
                "need_confirmed": False
            },
            ensure_ascii=False
        )
    return None


def dispatcher(command: str, type: str, only_path: str = "") -> str:
    path_filter_result = _filter_paths(command, only_path)
    if path_filter_result is not None:
        typer.echo(typer.style("[ERROR]触发非法路径检验", fg=typer.colors.RED))
        return path_filter_result

    if type in ("File", "Web", "Memory") and only_path:
        return json.dumps(
            {
                "success": False,
                "tool_id": None,
                "summary": "仅Code操作可以使用only_path",
                "data": None,
                "need_confirmed": False
            },
            ensure_ascii=False
        )

    if only_path:
        if only_path in _DISALLOWED_DIR:
            return json.dumps(
                {
                    "success": False,
                    "tool_id": None,
                    "summary": f"安全拦截：禁止挂载敏感路径 {only_path}",
                    "data": None,
                    "need_confirmed": False
                },
                ensure_ascii=False
            )
        try:
            resolve_safe_path(only_path, "real")
        except SecurityException as e:
            return json.dumps(
                {
                    "success": False,
                    "tool_id": None,
                    "summary": f"路径不合法: {e}",
                    "data": None,
                    "need_confirmed": False
                },
                ensure_ascii=False
            )

    task = command
    if only_path:
        task = f"{command}\n【工作路径: {only_path}】"

    try:
        if type == "File":
            result = file_agent.run(task)
        elif type == "Code":
            result = code_agent.run(task)
        elif type == "Web":
            result = web_agent.run(task)
        elif type == "Memory":
            result = memory_agent.run(task)
        else:
            return json.dumps(
                {
                    "success": False,
                    "tool_id": None,
                    "summary": "type必须为File/Code/Web/Memory",
                    "data": None,
                    "need_confirmed": False
                },
                ensure_ascii=False
            )
    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "tool_id": type,
                "summary": f"{type} Agent 异常: {e}",
                "data": None,
                "need_confirmed": False
            },
            ensure_ascii=False
        )

    return result


DISPATCHER_SCHEMA = {
    "type": "function",
    "function": {
        "name": "dispatcher",
        "description": "将任务分发到对应的子Agent执行。时间查询、网络搜索、网页抓取、下载、浏览器操作→Web；运行代码文件、数学计算→Code；文件读写/编辑→File；知识库→Memory。Code类型才需填写only_path。不确定时默认选Web。",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "自然语言任务描述",
                },
                "type": {
                    "type": "string",
                    "enum": ["File", "Code", "Web", "Memory"],
                    "description": "目标Agent类型。Web=网络搜索/时间查询/下载/抓取/浏览器；Code=执行代码文件/数学计算/Shell；File=文件读写；Memory=知识库。时间、搜索、下载、网页操作一律用Web不要用Code。",
                },
                "only_path": {
                    "type": "string",
                    "description": "仅Code类型填写：沙箱挂载的单个最小绝对路径。独立脚本挂载文件本身，项目挂载目录。不允许挂载用户家目录或桌面目录，其他类型传空字符串。",
                },
            },
            "required": ["command", "type"],
        },
    },
}
