import os
import typer
import json
from src.security.path_safety import resolve_safe_path
from src.utils.exceptions import SecurityException


def create_file(path: str, filename: str) -> str:
    if filename.endswith(".pdf") or filename.endswith(".docx"):
        return json.dumps(
            {
                "success": False, 
                "summary": "不支持创建PDF文件或docx文件"
            }, 
            ensure_ascii=False
        )
        
    try:
        path = resolve_safe_path(path)
    except SecurityException as e:
        return json.dumps(
            {
                "success": False, 
                "summary": str(e)
            }, 
            ensure_ascii=False
        )
        
    if os.path.isfile(path):
        return json.dumps(
            {
                "success": False, 
                "summary": f"父路径 {path} 是文件而非目录"
            }, 
            ensure_ascii=False
        )
        
    if not os.path.exists(path):
        return json.dumps(
            {
                "success": False, 
                "summary": f"目录 {path} 不存在，请先创建"
            }, 
            ensure_ascii=False
        )
        
    file_path = os.path.join(path, filename)
    if os.path.exists(file_path):
        return json.dumps(
            {
                "success": False, 
                "summary": f"文件 {file_path} 已存在，此操作会覆盖已有文件，需额外确认"
            }, 
            ensure_ascii=False
        )
        
    try:
        with open(file_path, "w") as f:
            pass
        return json.dumps(
            {
                "success": True, 
                "summary": f"空文件创建成功: {file_path}"
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


CREATE_FILE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "create_file",
        "description": "在指定路径创建新空文件。如果文件已存在，此操作会覆盖原文件。【此工具需要用户确认后方可执行——尤其是覆盖已有文件时】",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "父目录绝对路径"},
                "filename": {"type": "string", "description": "新文件名（含扩展名）"},
            },
            "required": ["path", "filename"],
        },
    },
}
