import json
import os
from src.tools.tools_registry import get_tools_registry
from src.utils.load_prompt import get_prompt_loader
from src.utils.path_policy import resolve_path
from src.utils.exceptions import SecurityException

def write(file_path: str, content: str, description: str = "") -> str:
    if file_path.lower().endswith((".pdf", ".docx")):
        return json.dumps(
            {
                "success": False,
                "error": "不支持写PDF文件或docx文件"
            },
            ensure_ascii=False
        )
    try:
        file_path = resolve_path(file_path, must_exist=False, write=True)

        # O_NOFOLLOW：校验与落盘之间即使被替换成符号链接也不会跟随，闭合 TOCTOU
        fd = os.open(file_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o644)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
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
        "description": get_prompt_loader().load_tool_manual("write"),
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "文件绝对路径（支持 ~ 展开），如 ~/test.txt"},
                "content": {"type": "string", "description": "要写入的内容（完全替换）"},
                "description": {"type": "string", "description": "用自然语言描述本次调用要做什么，会显示在终端"},
            },
            "required": ["file_path", "content", "description"],
        },
    },
}

get_tools_registry().register_tool("write", write, WRITE_SCHEMA, hitl=True, for_agent="Brain_Agent")
