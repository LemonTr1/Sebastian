import os
import json
from src.security.path_safety import resolve_safe_path
from src.utils.exceptions import SecurityException
from src.tools.tools_registry import get_tools_registry

def read(file_path: str, offset: int = -1, limit: int = -1) -> str:
    if (offset == -1 and limit != -1) or (offset != -1 and limit == -1):
        return json.dumps({
            "success": False,
            "error": "offset和limit必须同时设置或同时不设置",
        }, ensure_ascii=False)

    if file_path.endswith(".pdf") or file_path.endswith(".docx"):
        return json.dumps(
            {
                "success": False,
                "summary": "不支持读取pdf或docx文档操作",
                "content": None
            },
            ensure_ascii=False
        )
    file_path = os.path.abspath(file_path)
    try:
        file_path = resolve_safe_path(file_path)
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
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        #进行裁剪
        if offset != -1 and limit != -1:
            lines = content.splitlines()
            if offset < 1 or limit < 1:
                return json.dumps(
                    {
                        "success": False,
                        "summary": "offset和limit必须大于0",
                        "content": None
                    },
                    ensure_ascii=False
                )
            start_index = offset - 1
            end_index = min(start_index + limit, len(lines)-1)
            content = ""
            for index in range(start_index, end_index+1):
                content += f"{index+1}:  {lines[index]} \n"

        return json.dumps(
            {
                "success": True,
                "summary": f"文件 {file_path} 读取成功",
                "content": content
            },
            ensure_ascii=False
        )
    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "summary": str(e),
                "content": None
            },
            ensure_ascii=False
        )


READ_SCHEMA = {
    "type": "function",
    "function": {
        "name": "read",
        "description": "读取文件内容，如果不传offset和limit参数表示读取完整文件内容，如果要传则必须同时设置offset和limit。",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "文件绝对路径，如 /home/user/file.txt"},
                "offset": {"type": "integer", "description": "文件文本内容的起始行，如从第10行开始读取，必须大于0"},
                "limit": {"type": "integer", "description": "读取的行数，如读取20行，若从第10行开始读则一共读取第10行到第29行的文本内容，必须大于0"}
            },
            "required": ["file_path"],
        },
    },
}

get_tools_registry().register_tool("read", read, READ_SCHEMA, for_agent="Brain_Agent")
