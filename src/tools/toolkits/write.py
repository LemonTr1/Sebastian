import json
from src.tools.tools_registry import get_tools_registry
from src.security.path_safety import resolve_safe_path
from src.utils.exceptions import SecurityException

def write(file_path: str, content: str) -> str:
    if file_path.endswith(".pdf") or file_path.endswith(".docx"):
        return json.dumps(
            {
                "success": False,
                "error": "不支持写PDF文件或docx文件"
            },
            ensure_ascii=False
        )
    try:
        file_path = resolve_safe_path(file_path, must_exist=False)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return json.dumps(
            {
                "success": True,
                "summary": f"文件 {file_path} 内容已写入成功"
            },
            ensure_ascii=False
        )
    except SecurityException as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)
    except FileNotFoundError:
        return json.dumps({
            "success": False,
            "error": f"文件 {file_path} 不存在"
        }, ensure_ascii=False)
    except PermissionError:
        return json.dumps({
            "success": False,
            "error": f"没有权限写入文件 {file_path}"
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"错误：{str(e)}"
        }, ensure_ascii=False)


WRITE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "write",
        "description": "将提供的内容写入文件。如果文件不存在，则创建它。如果已存在，则替换其先前的全部内容。【此工具需要用户确认后方可执行】",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "目标文件的绝对路径，如 /home/user/test.txt"},
                "content": {"type": "string", "description": "要写入的内容（完全替换）"},
            },
            "required": ["file_path", "content"],
        },
    },
}

get_tools_registry().register_tool("write", write, WRITE_SCHEMA, hitl=True, for_agent="Brain_Agent")
