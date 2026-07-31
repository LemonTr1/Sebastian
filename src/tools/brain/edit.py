import json
from src.security.path_safety import resolve_safe_path
from src.utils.exceptions import SecurityException
from src.tools.tools_registry import get_tools_registry


def edit(file_path: str, old_text: str, new_text: str, replace_all: bool = False) -> str:
    # 不支持二进制/文档格式
    if file_path.endswith(".pdf") or file_path.endswith(".docx") or file_path.endswith(".pptx"):
        return json.dumps(
            {
                "success": False,
                "summary": "不支持编辑PDF/DOCX/PPTX文件, 请使用 dispatcher('File') 处理文档"
            },
            ensure_ascii=False
        )

    if not old_text:
        return json.dumps(
            {
                "success": False,
                "summary": "old_text 不能为空，请指定要查找的旧文本"
            },
            ensure_ascii=False
        )

    try:
        safe_path = resolve_safe_path(file_path)
    except SecurityException as e:
        return json.dumps(
            {
                "success": False,
                "summary": str(e)
            },
            ensure_ascii=False
        )

    try:
        with open(safe_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return json.dumps(
            {
                "success": False,
                "summary": f"文件 {file_path} 不存在或不是一个有效的文件"
            },
            ensure_ascii=False
        )
    except PermissionError:
        return json.dumps(
            {
                "success": False,
                "summary": f"没有权限读取文件 {file_path}"
            },
            ensure_ascii=False
        )
    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "summary": f"读取文件出错: {str(e)}"
            },
            ensure_ascii=False
        )

    if old_text not in content:
        return json.dumps(
            {
                "success": False,
                "summary": f"未在文件中找到待替换文本: {old_text[:50]}"
            },
            ensure_ascii=False
        )

    count = content.count(old_text)

    if not replace_all and count > 1:
        return json.dumps(
            {
                "success": False,
                "summary": "有多个匹配结果，提高匹配细粒度"
            },
            ensure_ascii=False
        )

    if replace_all:
        new_content = content.replace(old_text, new_text)
    else:
        new_content = content.replace(old_text, new_text, 1)
        count = 1

    try:
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(new_content)
    except PermissionError:
        return json.dumps(
            {
                "success": False,
                "summary": f"没有权限写入文件 {file_path}"
            },
            ensure_ascii=False
        )
    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "summary": f"写入文件出错: {str(e)}"
            },
            ensure_ascii=False
        )

    return json.dumps(
        {
            "success": True,
            "summary": f"文件 {file_path} 编辑成功，共替换 {count} 处"
        },
        ensure_ascii=False
    )


EDIT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "edit",
        "description": "在指定文本文件中查找 old_text 并将其替换为 new_text。默认只替换第一处；设置 replace_all=True 可替换所有出现的位置。此操作会直接修改文件内容。【此工具需要用户确认后方可执行】",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "目标文件的绝对路径，如 /home/user/test.txt"},
                "old_text": {"type": "string", "description": "要查找的旧文本，不能为空"},
                "new_text": {"type": "string", "description": "替换后的新文本"},
                "replace_all": {"type": "boolean", "description": "是否替换所有匹配项，true=全部替换，false=仅替换第一处，默认false"},
            },
            "required": ["file_path", "old_text", "new_text"],
        },
    },
}

get_tools_registry().register_tool("edit", edit, EDIT_SCHEMA, hitl=True, for_agent="Brain_Agent")
