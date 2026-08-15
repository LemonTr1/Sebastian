import json
import glob as g
from pathlib import Path
from src.security.path_safety import resolve_safe_path
from src.utils.exceptions import SecurityException
from src.tools.tools_registry import get_tools_registry

MAX_RESULTS = 60

def glob(pattern: str, scope: str) -> str:
    try:
        # 安全检查
        safe_scope = resolve_safe_path(scope)
    except SecurityException as e:
        return json.dumps(
            {
                "success": False,
                "summary": str(e),
                "content": None
            },
            ensure_ascii=False
        )

    try:
        # 使用glob在指定目录进行文件匹配
        matched_files = g.glob(pattern, root_dir=safe_scope, recursive=True)

        # 过滤匹配结果，确保所有文件都在指定的scope目录下
        filtered_files = [f for f in matched_files if Path(f).is_relative_to(safe_scope)]

        if len(filtered_files) > MAX_RESULTS:
            return json.dumps(
                {
                    "success": True,
                    "summary": f"匹配到 {len(filtered_files)} 个文件，结果过多，仅显示前 {MAX_RESULTS} 个，请缩小匹配范围或使用更具体的模式",
                    "content": filtered_files[:MAX_RESULTS]
                },
                ensure_ascii=False
            )

        return json.dumps(
            {
                "success": True,
                "summary": f"匹配到 {len(filtered_files)} 个文件",
                "content": filtered_files
            },
            ensure_ascii=False
        )

    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "summary": f"文件匹配失败：{e}",
                "content": None
            },
            ensure_ascii=False
        )

GLOB_SCHEMA = {
    "type": "function",
    "function": {
        "name": "glob",
        "description": "根据模式在指定目录下匹配文件，返回匹配到的文件相对路径列表",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "模式匹配串，如'src/**/*.py'"},
                "scope": {"type": "string", "description": "查找范围，必须为目录且以绝对路径表示"}
            },
            "required": ["pattern", "scope"]
        }
    }
}

#注册工具
get_tools_registry().register_tool("glob", glob, GLOB_SCHEMA, for_agent="Brain_Agent")
