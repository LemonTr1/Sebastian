import os
import shutil
import json
from src.security.path_safety import resolve_safe_path
from src.utils.exceptions import SecurityException


def cp_file(src: str, dst: str) -> str:
    try:
        src = resolve_safe_path(src)
    except SecurityException as e:
        return json.dumps(
            {
                "success": False,
                "summary": str(e)
            },
            ensure_ascii=False
        )
    if not os.path.isfile(src):
        return json.dumps(
            {
                "success": False,
                "summary": f"源路径不是文件: {src}"
            },
            ensure_ascii=False
        )
    try:
        dst = resolve_safe_path(os.path.dirname(dst)) if os.path.dirname(dst) else ""
    except SecurityException as e:
        return json.dumps(
            {
                "success": False,
                "summary": str(e)
            },
            ensure_ascii=False
        )
    try:
        if os.path.isdir(dst):
            shutil.copy2(src, os.path.join(dst, os.path.basename(src)))
            return json.dumps(
                {
                    "success": True,
                    "summary": f"文件复制成功: {src} -> {dst}/"
                },
                ensure_ascii=False
            )
        else:
            shutil.copy2(src, dst)
            return json.dumps(
                {
                    "success": True,
                    "summary": f"文件复制成功: {src} -> {dst}"
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


def cp_dir(src: str, dst: str) -> str:
    try:
        src = resolve_safe_path(src)
        dst = resolve_safe_path(dst)
    except SecurityException as e:
        return json.dumps(
            {
                "success": False,
                "summary": str(e)
            },
            ensure_ascii=False
        )
    if not os.path.isdir(src):
        return json.dumps(
            {
                "success": False,
                "summary": f"源路径不是目录: {src}"
            },
            ensure_ascii=False
        )
    target = os.path.join(dst, os.path.basename(src))
    try:
        shutil.copytree(src, target)
        return json.dumps(
            {
                "success": True,
                "summary": f"目录复制成功: {src} -> {target}"
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


COPY_FILE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "cp_file",
        "description": "复制单个文件到目标路径",
        "parameters": {
            "type": "object",
            "properties": {
                "src": {"type": "string", "description": "源文件绝对路径"},
                "dst": {"type": "string", "description": "目标路径（目录或文件）"},
            },
            "required": ["src", "dst"],
        },
    },
}

COPY_DIR_SCHEMA = {
    "type": "function",
    "function": {
        "name": "cp_dir",
        "description": "复制整个目录到目标路径",
        "parameters": {
            "type": "object",
            "properties": {
                "src": {"type": "string", "description": "源目录绝对路径"},
                "dst": {"type": "string", "description": "目标父目录绝对路径"},
            },
            "required": ["src", "dst"],
        },
    },
}
