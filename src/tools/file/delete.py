import os
import shutil
import json
from pathlib import Path
from src.security.path_safety import resolve_safe_path
from src.utils.exceptions import SecurityException
from src.tools.tools_registry import get_tools_registry

HOME = Path.home()


def delete_file(path: str, filename: str) -> str:
    path = os.path.abspath(path)
    file_path = os.path.join(path, filename)
    try:
        resolve_safe_path(file_path)
    except SecurityException as e:
        return json.dumps(
            {
                "success": False,
                "summary": str(e)
            },
            ensure_ascii=False
        )
    if not Path(file_path).is_relative_to(HOME):
        return json.dumps(
            {
                "success": False,
                "summary": f"目标必须在 {HOME} 下"
            },
            ensure_ascii=False
        )
    try:
        if os.path.islink(file_path):
            os.unlink(file_path)
        elif os.path.isfile(file_path):
            os.remove(file_path)
        elif os.path.isdir(file_path):
            shutil.rmtree(file_path)
        else:
            return json.dumps(
                {
                    "success": False,
                    "summary": f"路径不存在: {file_path}"
                },
                ensure_ascii=False
            )
        return json.dumps(
            {
                "success": True,
                "summary": f"删除成功: {file_path}"
            },
            ensure_ascii=False
        )
    except PermissionError as e:
        return json.dumps(
            {
                "success": False,
                "summary": f"权限不足: {e}"
            },
            ensure_ascii=False
        )
    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "summary": str(e)
            },
            ensure_ascii=False
        )


DELETE_FILE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "delete_file",
        "description": "删除文件或目录。【此工具需要用户确认后方可执行——删除不可逆！】",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "父目录绝对路径"},
                "filename": {"type": "string", "description": "要删除的文件或目录名称"},
            },
            "required": ["path", "filename"],
        },
    },
}

get_tools_registry().register_tool("delete_file", delete_file, DELETE_FILE_SCHEMA, hitl=True, for_agent="File_Agent")
