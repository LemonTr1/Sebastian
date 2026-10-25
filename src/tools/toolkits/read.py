import os
import json
import base64
from src.security.path_safety import resolve_safe_path
from src.utils.exceptions import SecurityException
from src.tools.tools_registry import get_tools_registry

# 支持的可视图片格式：文件大小上限（字节），防止超大图撑爆上下文
MAX_IMAGE_BYTES = 15 * 1024 * 1024

# 文本文件一次性读取上限：超限时要求调用方用 offset/limit 分片
MAX_TEXT_BYTES = 10 * 1024 * 1024

# 扩展名 -> MIME；优先使用显式映射，避免依赖系统 mimetypes 配置缺失
EXTENSION_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
}

# 文件头魔数 -> MIME；扩展名缺失/未知（如截图临时文件、无后缀的 blob）时按内容识别
MAGIC_MIME = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


def _sniff_image_mime(file_path: str) -> str | None:
    """按文件头判断是否为图片，返回 MIME 或 None。"""
    try:
        with open(file_path, "rb") as f:
            head = f.read(16)
    except Exception:
        return None

    for magic, mime in MAGIC_MIME:
        if head.startswith(magic):
            return mime
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "image/webp"
    # BMP 的 "BM" 只有两字节，容易被文本误命中，额外校验保留字段必须为 0
    if head.startswith(b"BM") and head[6:8] == b"\x00\x00":
        return "image/bmp"
    return None


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

    if offset != -1 and (offset < 1 or limit < 1):
        return json.dumps({
            "success": False,
            "summary": "offset和limit必须大于0",
            "content": None,
        }, ensure_ascii=False)

    if file_path.lower().endswith((".pdf", ".docx")):
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
    mime = EXTENSION_MIME.get(ext) or _sniff_image_mime(file_path)
    if mime:
        return _read_image(file_path, mime)

    try:
        if offset == -1:
            size = os.path.getsize(file_path)
            if size > MAX_TEXT_BYTES:
                return json.dumps(
                    {
                        "success": False,
                        "summary": (
                            f"文件过大（{size / 1024 / 1024:.1f}MB），超过单次读取上限 "
                            f"{MAX_TEXT_BYTES / 1024 / 1024:.0f}MB，请使用 offset/limit 分片读取"
                        ),
                        "content": None,
                    },
                    ensure_ascii=False,
                )
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        else:
            # 分片读取：逐行流式扫描，不把整文件载入内存
            chunks = []
            with open(file_path, "r", encoding="utf-8") as f:
                for index, line in enumerate(f, 1):
                    if index < offset:
                        continue
                    if index > offset + limit - 1:
                        break
                    # 不能在 f-string 表达式里用反斜杠（Python 3.10 兼容）
                    text_line = line.rstrip("\r\n")
                    chunks.append(f"{index}:  {text_line} \n")
            content = "".join(chunks)
            if not content:
                with open(file_path, "r", encoding="utf-8") as f:
                    total = sum(1 for _ in f)
                return json.dumps(
                    {
                        "success": False,
                        "summary": f"offset 超出文件行数（共 {total} 行）",
                        "content": None,
                    },
                    ensure_ascii=False,
                )

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


def _read_image(file_path: str, mime: str) -> dict:
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
        "description": "读取文件内容。文本文件：不传offset和limit参数表示读取完整文件内容（单次上限10MB，超出请分片），如果要传则必须同时设置offset和limit。图片文件（png/jpg/jpeg/webp/gif/bmp，≤15MB，无扩展名或扩展名未知时按文件头识别）：以图片形式加载给视觉模型，用于识别、描述、解读图片内容，一轮任务需要看多张图时必须在同一批工具调用里并行读完所有待读图片，严禁一张一张分轮读",
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
