import os
import json
import base64
from src.security.path_safety import resolve_safe_path
from src.utils.exceptions import SecurityException
from src.tools.tools_registry import get_tools_registry

# 支持的可视图片格式：文件大小上限（字节），防止超大图撑爆上下文
MAX_IMAGE_BYTES = 15 * 1024 * 1024

# 扩展名 -> MIME；优先使用显式映射，避免依赖系统 mimetypes 配置缺失
EXTENSION_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
}


def read(file_path: str, offset: int = -1, limit: int = -1) -> str | dict:
    """读取文件。

    文本文件：返回 JSON 字符串（content 为文本内容，offset/limit 控制分片）。
    图片文件：返回带 __multimodal__ 标记的 dict，由 AgentRunner 把 content 直接替换为
    content-parts 列表（image_url + base64 data URI），让视觉模型真正看到图片。
    """
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

    ext = os.path.splitext(file_path)[1].lower()
    if ext in EXTENSION_MIME:
        return _read_image(file_path, ext)

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


def _read_image(file_path: str, ext: str) -> dict:
    """把本地图片编码为多模态 content-parts（text + image_url data URI）。"""
    try:
        size = os.path.getsize(file_path)
    except OSError as e:
        return _image_error(f"无法读取文件大小：{e}")
    if size > MAX_IMAGE_BYTES:
        return _image_error(f"图片过大：{size / 1024 / 1024:.1f}MB，超过上限 {MAX_IMAGE_BYTES / 1024 / 1024:.0f}MB")

    try:
        with open(file_path, "rb") as f:
            raw = f.read()
    except Exception as e:
        return _image_error(f"读取文件失败：{e}")

    mime = EXTENSION_MIME[ext]
    data_uri = "data:{mime};base64,{b64}".format(
        mime=mime, b64=base64.b64encode(raw).decode("ascii")
    )

    return {
        "__multimodal__": True,
        "parts": [
            {"type": "text", "text": f"已加载图片 {file_path}（{mime}，{size / 1024:.0f}KB）<SYSTEM_REMINDER>请在同一批工具调用中一次性读完所有需要的图片，否则在下一轮工具调用中如果重新使用该工具则旧图片信息会被压缩。</SYSTEM_REMINDER>"},
            {"type": "image_url", "image_url": {"url": data_uri}},
        ],
    }


def _image_error(msg: str) -> dict:
    return {
        "__multimodal__": True,
        "parts": [
            {"type": "text", "text": json.dumps({"success": False, "summary": msg}, ensure_ascii=False)}
        ],
    }


READ_SCHEMA = {
    "type": "function",
    "function": {
        "name": "read",
        "description": "读取文件内容。文本文件：不传offset和limit参数表示读取完整文件内容，如果要传则必须同时设置offset和limit。图片文件（png/jpg/jpeg/webp/gif/bmp，≤15MB）：以图片形式加载给视觉模型，用于识别、描述、解读图片内容，一轮任务需要看多张图时必须在同一批工具调用里并行读完所有待读图片，严禁一张一张分轮读",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "文件绝对路径，如 /home/user/file.txt 或 /home/user/a.png"},
                "offset": {"type": "integer", "description": "文件文本内容的起始行，如从第10行开始读取，必须大于0"},
                "limit": {"type": "integer", "description": "读取的行数，如读取20行，若从第10行开始读则一共读取第10行到第29行的文本内容，必须大于0"}
            },
            "required": ["file_path"],
        },
    },
}

get_tools_registry().register_tool("read", read, READ_SCHEMA, for_agent="Brain_Agent")
