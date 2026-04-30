import os
import json
import httpx
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from urllib.parse import urlparse, unquote
from agents import function_tool
import typer

# 配置项：你可以根据环境修改
ALLOWED_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.gif', '.docx', '.xlsx', '.txt', '.csv', '.zip', '.tar', '.gz', '.7z', '.tar.gz', '.tgz'}
COMPOUND_EXTENSIONS = ['.tar.gz', '.tar.bz2', '.tar.xz', '.tgz']
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
#默认下载路径
DEFAULT_DOWNLOAD_DIR = Path("/home/lem0ntr1/下载/")
DEFAULT_TIMEOUT = 600  # 10分钟

def _safe_filename(url: str, content_type: str = None) -> str:
    """从URL或Content-Type推断安全文件名"""
    # 尝试从URL路径提取
    path = urlparse(url).path
    filename = unquote(Path(path).name)
    if filename:
        lower_name = filename.lower()
        for comp_ext in COMPOUND_EXTENSIONS:
            if lower_name.endswith(comp_ext):
                return filename
        _, ext = os.path.splitext(filename)
        if ext.lower() in ALLOWED_EXTENSIONS:
            return filename
    # 如果URL无法提取，用Content-Type推断扩展名
    ext_map = {
        'application/pdf': '.pdf',
        'image/png': '.png',
        'image/jpeg': '.jpg',
        'image/gif': '.gif',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
        'text/plain': '.txt',
        'text/csv': '.csv',
        'application/zip': '.zip'
    }
    if content_type:
        ext = ext_map.get(content_type.split(';')[0].strip())
        if ext:
            return f"downloaded_file{ext}"
    return None  # 不允许未知类型

def _download_file(url: str, save_dir: str) -> dict:
    """实际下载逻辑，运行在线程中"""
    with httpx.Client(follow_redirects=True, timeout=DEFAULT_TIMEOUT) as client:
        # 先用HEAD获取基本信息，但不强制
        try:
            head_resp = client.head(url)
            content_type = head_resp.headers.get('content-type', '')
            content_length = head_resp.headers.get('content-length')
        except Exception:
            content_type = ''
            content_length = None

        # 确定文件名
        filename = _safe_filename(url, content_type)
        if not filename:
            return {"success": False, "error": f"不支持的文件类型或无法识别类型: {content_type}"}

        # 检查文件大小（如果服务器提供了）
        if content_length and int(content_length) > MAX_FILE_SIZE:
            return {"success": False, "error": f"文件大小 {int(content_length)} 超过限制 {MAX_FILE_SIZE}"}

        # 流式下载并检查实际大小
        total = int(content_length) if content_length else None
        save_path = Path(save_dir) / filename
        save_path.parent.mkdir(parents=True, exist_ok=True)

        with client.stream("GET", url) as response:
            response.raise_for_status()
            downloaded = 0
            with open(save_path, 'wb') as f:
                # 创建进度条，长度设为总字节数
                with typer.progressbar(length=total, label="正在下载") as progress:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)
                        downloaded += len(chunk)
                        # 更新进度条
                        if total:
                            progress.update(len(chunk))
                        if downloaded > MAX_FILE_SIZE:
                            f.close()
                            os.remove(save_path)
                            return {"success": False, "error": f"文件超过 {MAX_FILE_SIZE} 字节，已中断"}
            actual_size = downloaded

        typer.echo(typer.style(f"[执行中]下载完成",fg=typer.colors.WHITE))
        return {
            "success": True,
            "filename": filename,
            "save_path": str(save_path.absolute()),
            "size": actual_size,
            "content_type": response.headers.get('content-type', content_type)
        }

@function_tool
def download_file(url: str, save_dir: str = None, timeout: int = DEFAULT_TIMEOUT) -> str:
    """
    下载网络文件到本地。支持常见文档、图片、表格等。
    当用户要求获取、下载某个链接的文件时，应调用此工具。

    Args:
        url: 文件的直接下载链接。
        save_dir: 保存目录，默认为 ./downloads。
        timeout: 超时秒数，默认30。

    Returns:
        JSON字符串，包含成功信息或错误提示。成功时:
        {
            "success": true,
            "filename": "example.pdf",
            "save_path": "/abs/path/example.pdf",
            "size": 1024,
            "content_type": "application/pdf"
        }
    """
    if not save_dir:
        save_dir = str(DEFAULT_DOWNLOAD_DIR)

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_download_file, url, save_dir)
            result = future.result(timeout=timeout)
        return json.dumps(result, ensure_ascii=False)
    except FutureTimeoutError:
        return json.dumps({"success": False, "error": "下载超时"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": f"下载失败: {str(e)}"}, ensure_ascii=False)