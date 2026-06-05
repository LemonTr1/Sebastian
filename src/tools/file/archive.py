import os
import shutil
import json
from src.security.path_safety import resolve_safe_path
from src.utils.exceptions import SecurityException


def make_archive(source_path: str, output_path: str, archive_format: str) -> str:
    try:
        source_path = resolve_safe_path(source_path)
    except SecurityException as e:
        return json.dumps(
            {
                "success": False,
                "summary": str(e)
            },
            ensure_ascii=False
        )
    try:
        base = os.path.splitext(output_path)[0]
        result_path = shutil.make_archive(base, archive_format, source_path)
        return json.dumps(
            {
                "success": True,
                "summary": f"压缩成功: {result_path}"
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


def unpack_archive(archive_path: str, extract_dir: str, archive_format: str = "") -> str:
    try:
        extract_dir = resolve_safe_path(extract_dir)
    except SecurityException as e:
        return json.dumps(
            {
                "success": False,
                "summary": str(e)
            },
            ensure_ascii=False
        )
    if not archive_format and archive_path.endswith(".7z"):
        try:
            import py7zr
            with py7zr.SevenZipFile(archive_path, mode="r") as z:
                z.extractall(path=extract_dir)
            return json.dumps(
                {
                    "success": True,
                    "summary": f"解压成功: {archive_path} -> {extract_dir}"
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
    try:
        if archive_format:
            shutil.unpack_archive(archive_path, extract_dir, archive_format)
        else:
            shutil.unpack_archive(archive_path, extract_dir)
        return json.dumps(
            {
                "success": True,
                "summary": f"解压成功: {archive_path} -> {extract_dir}"
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


MAKE_ARCHIVE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "make_archive",
        "description": "压缩目录或文件。支持的格式: zip, tar, gztar, bztar, xztar",
        "parameters": {
            "type": "object",
            "properties": {
                "source_path": {"type": "string", "description": "要压缩的源目录/文件绝对路径"},
                "output_path": {"type": "string", "description": "输出压缩包路径（不含扩展名）"},
                "archive_format": {"type": "string", "description": "压缩格式: zip, tar, gztar, bztar, xztar"},
            },
            "required": ["source_path", "output_path", "archive_format"],
        },
    },
}

UNPACK_ARCHIVE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "unpack_archive",
        "description": "解压压缩包到指定目录。支持 zip, tar, gz, bz2, xz, 7z 等格式",
        "parameters": {
            "type": "object",
            "properties": {
                "archive_path": {"type": "string", "description": "压缩包文件绝对路径"},
                "extract_dir": {"type": "string", "description": "解压目标目录绝对路径"},
                "archive_format": {"type": "string", "description": "显式指定格式（可选），留空自动检测"},
            },
            "required": ["archive_path", "extract_dir"],
        },
    },
}
