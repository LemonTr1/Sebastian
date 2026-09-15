import os
import mimetypes
import base64
import json
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


def view_image(file_path: str) -> dict:
    """读取本地图片并以 OpenAI 多模态 content 形式返回，供具备视觉能力的模型"查看"。

    返回 dict 带 __multimodal__ 标记，由 AgentRunner 识别后把 content 直接替换为
    content-parts 列表（image_url + base64 data URI），从而让视觉模型真正看到图片。
    """
    try:
        safe_path = resolve_safe_path(os.path.abspath(file_path))
    except SecurityException as e:
        return _error(str(e))

    ext = os.path.splitext(safe_path)[1].lower()
    if ext not in EXTENSION_MIME:
        return _error(f"不支持的文件类型：{ext or '无扩展名'}，支持的图片格式：{', '.join(sorted(EXTENSION_MIME))}")

    try:
        size = os.path.getsize(safe_path)
    except OSError as e:
        return _error(f"无法读取文件大小：{e}")
    if size > MAX_IMAGE_BYTES:
        return _error(f"图片过大：{size / 1024 / 1024:.1f}MB，超过上限 {MAX_IMAGE_BYTES / 1024 / 1024:.0f}MB")

    try:
        with open(safe_path, "rb") as f:
            raw = f.read()
    except Exception as e:
        return _error(f"读取文件失败：{e}")

    mime = EXTENSION_MIME[ext]
    data_uri = "data:{mime};base64,{b64}".format(
        mime=mime, b64=base64.b64encode(raw).decode("ascii")
    )

    return {
        "__multimodal__": True,
        "parts": [
            {"type": "text", "text": f"已加载图片 {safe_path}（{mime}，{size / 1024:.0f}KB）<SYSTEM_REMINDER>请在同一批工具调用中一次性读完所有需要的图片，否则在下一轮工具调用中如果重新使用该工具则旧图片信息会被压缩。</SYSTEM_REMINDER>"},
            {"type": "image_url", "image_url": {"url": data_uri}},
        ],
    }


def _error(msg: str) -> dict:
    return {
        "__multimodal__": True,
        "parts": [
            {"type": "text", "text": json.dumps({"success": False, "summary": msg}, ensure_ascii=False)}
        ],
    }


VIEW_IMAGE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "view_image",
        "description": "查看本地图片文件（png/jpg/jpeg/webp/gif/bmp），以图片形式加载给视觉模型，用于识别、描述、解读图片内容。一轮任务需要看多张图时，必须在同一批工具调用里并行读完所有待读图片，严禁一张一张分轮读",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "图片文件的绝对路径，如 /home/user/a.png"}
            },
            "required": ["file_path"],
        },
    },
}

get_tools_registry().register_tool("view_image", view_image, VIEW_IMAGE_SCHEMA, for_agent="Brain_Agent")