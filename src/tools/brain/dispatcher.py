import os
import re
import json
from pathlib import Path
import typer
from src.security.path_safety import resolve_safe_path
from src.utils.exceptions import SecurityException
from src.tools.tools_registry import get_tools_registry

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
    from src.agents.file_agent import file_agent
    from src.agents.code_agent import code_agent
    from src.agents.web_agent import web_agent
    from src.agents.memory_agent import memory_agent

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
        project_name = os.path.basename(only_path)
        task = f"{command}\n <SYSTEM_REMINDER>工具`execute_in_sandbox`中的`code_file_path`参数使用`{only_path}`挂载到`/workspace/{project_name}`<SYSTEM_REMINDER>"
    elif type == "Code":
        _SCRIPT_EXT_RE = re.compile(
            r'(?:[^\s]*\.(?:py|sh|bash|c|cpp|cc|cxx|java|go|rs|js|ts|rb|pl|r|swift))',
            re.IGNORECASE
        )
        clean = _strip_quoted_content(command)
        if _SCRIPT_EXT_RE.search(clean):
            return json.dumps(
                {
                    "success": False,
                    "tool_id": None,
                    "summary": (
                        "缺少 only_path 参数。命令中引用了脚本文件，"
                        "Code 类型必须通过 only_path 将脚本的绝对路径挂载到沙箱，否则沙箱内无法访问该文件。"
                        "请使用 only_path=\"脚本文件的绝对路径\" 重新调用 dispatcher。"
                        "纯计算（如 python3 -c \"print(1+1)\"）可以不传 only_path。"
                    ),
                    "data": None,
                    "need_confirmed": False
                },
                ensure_ascii=False
            )

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
        "description": (
            "将任务分发到对应的子Agent执行。\n"
            "路由规则（按优先级）：运行脚本→Code，先写后运行→File→Code，执行并保存→Code→File，"
            "文件读写/文档→File，搜索/下载/时间/浏览器/网页→Web，知识库→Memory。\n"
            "如果意图涉及脚本执行，优先选择Code。\n"
            "only_path仅Code类型填写：沙箱挂载的单个最小绝对路径。"
            "独立脚本挂载文件本身，项目挂载目录。纯计算传空。"
            "禁止挂载：用户家目录、桌面、.ssh/.gnupg等敏感路径。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "自然语言任务描述。用Markdown代码块包裹代码/Shell命令/文本内容。",
                },
                "type": {
                    "type": "string",
                    "enum": ["File", "Code", "Web", "Memory"],
                    "description": "目标Agent类型。Code=执行脚本/代码/Shell；File=文件读写/文档；Web=搜索/下载/浏览器/时间；Memory=知识库。",
                },
                "only_path": {
                    "type": "string",
                    "description": "仅Code类型填写：沙箱挂载的单个最小绝对路径。独立脚本挂载文件，项目挂载目录。不涉及文件则传空字符串。",
                },
            },
            "required": ["command", "type"],
        },
    },
}

#注册工具
get_tools_registry().register_tool("dispatcher", dispatcher, DISPATCHER_SCHEMA, for_agent="Brain_Agent")
