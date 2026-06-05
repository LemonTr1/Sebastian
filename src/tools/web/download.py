import os
import re
import io
import json
import gzip
import zipfile
import tarfile
import httpx
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from urllib.parse import urlparse, unquote
from src.security.url_safety import is_public_url

ALLOWED_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.gif', '.docx', '.xlsx', '.txt', '.csv', '.zip', '.tar', '.gz', '.7z', '.tar.gz', '.tgz'}
COMPOUND_EXTENSIONS = ['.tar.gz', '.tar.bz2', '.tar.xz', '.tgz']
MAX_FILE_SIZE = 100 * 1024 * 1024
DEFAULT_DOWNLOAD_DIR = Path(f"/home/{os.getlogin()}/下载/")
DEFAULT_TIMEOUT = 600

DANGEROUS_EXTENSIONS = {
    '.exe', '.bat', '.cmd', '.com', '.msi', '.vbs', '.ps1', '.psm1',
    '.sh', '.bash', '.csh', '.zsh', '.fish',
    '.dll', '.so', '.dylib',
    '.jar', '.class', '.pyc', '.pyo',
    '.deb', '.rpm', '.apk', '.ipa',
    '.scr', '.pif', '.reg', '.lnk',
    '.hta', '.wsf', '.cpl', '.msc',
}

MAGIC_BYTES = {
    b'\x89PNG':     ['.png'],
    b'\xff\xd8\xff': ['.jpg', '.jpeg'],
    b'GIF8':        ['.gif'],
    b'%PDF':        ['.pdf'],
    b'PK\x03\x04':  ['.zip', '.docx', '.xlsx', '.jar', '.apk'],
    b'\x1f\x8b':    ['.gz', '.tar.gz', '.tgz'],
}

SUSPICIOUS_DOUBLE_EXT = re.compile(r'\.\w{2,4}\.\w{2,4}$', re.IGNORECASE)

EXT_CONTENT_TYPE_MAP = {
    '.pdf': 'application/pdf', '.png': 'image/png', '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg', '.gif': 'image/gif',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.txt': 'text/plain', '.csv': 'text/csv', '.zip': 'application/zip',
    '.gz': 'application/gzip', '.tgz': 'application/gzip',
    '.tar': 'application/x-tar', '.tar.gz': 'application/gzip',
    '.7z': 'application/x-7z-compressed',
}

HARMFUL_MIME_TYPES = {
    'application/x-msdownload', 'application/x-msdos-program',
    'application/x-msi', 'application/x-sh',
    'application/x-shockwave-flash', 'application/x-java-applet',
    'application/x-ms-shortcut',
}

_TEXT_MALWARE_PATTERNS = [
    (re.compile(rb'<\?php\b', re.I), 'PHP webshell'),
    (re.compile(rb'\beval\s*\(\s*(?:\$|base64_decode)', re.I), '恶意eval()'),
    (re.compile(rb'\b(?:system|exec|passthru|shell_exec|popen|proc_open)\s*\(', re.I), 'PHP命令执行'),
    (re.compile(rb'\$_(?:GET|POST|REQUEST|COOKIE|SERVER|FILES)\b', re.I), 'PHP超全局注入'),
    (re.compile(rb'base64_decode\s*\(', re.I), 'Base64解码'),
    (re.compile(rb'\beval\s*\(', re.I), 'JS eval()'),
    (re.compile(rb'document\.write\s*\(\s*unescape', re.I), 'JS混淆'),
    (re.compile(rb'\b(?:__import__|compile|exec|eval)\s*\(', re.I), 'Python动态执行'),
    (re.compile(rb'\bsubprocess\.(?:call|Popen|run|check_output)\b', re.I), 'Python子进程'),
    (re.compile(rb'(?:wget|curl)\s.+\|\s*(?:sh|bash)', re.I), '远程脚本管道执行'),
    (re.compile(rb'nc\s.+-e\s+/bin/', re.I), 'Netcat反弹shell'),
    (re.compile(rb'mkfifo\s', re.I), '命名管道'),
    (re.compile(rb'>(?:\s*)/dev/(?:tcp|udp)/', re.I), '/dev/tcp反弹'),
    (re.compile(rb'xp_cmdshell\b', re.I), 'SQL cmdshell'),
]
_BASE64_PAYLOAD_RE = re.compile(rb'(?:[A-Za-z0-9+/]{60,}={0,2})')

_PDF_DANGEROUS_KEYS = [
    (b'/JavaScript', 'PDF JS'), (b'/Launch', 'PDF Launch'),
    (b'/EmbeddedFile', 'PDF嵌入文件'), (b'/OpenAction', 'PDF自动执行'),
    (b'/RichMedia', 'PDF RichMedia'), (b'/SubmitForm', 'PDF远程提交'),
]

_OFFICE_MACRO_MEMBERS = {
    'word/vbaproject.bin', 'word/vbadata.xml',
    'xl/vbaproject.bin', 'ppt/vbaproject.bin',
}


def _check_url_safety(url: str) -> str | None:
    if not is_public_url(url):
        return f"URL不安全：禁止访问内网地址"
    return None


def _check_save_dir(save_dir: str) -> str | None:
    raw = save_dir
    if ".." in raw:
        return f"save_dir包含路径遍历: {raw}"
    if raw.startswith("~"):
        return f"save_dir使用了~简写: {raw}"
    try:
        resolved = os.path.abspath(save_dir)
    except Exception:
        return f"save_dir无法解析: {raw}"
    if not Path(resolved).is_relative_to(Path.home()):
        return f"save_dir必须在用户目录下: {resolved}"
    return None


def _check_filename(filename: str) -> str | None:
    lower = filename.lower()
    for ext in COMPOUND_EXTENSIONS:
        if lower.endswith(ext):
            return None
    _, ext = os.path.splitext(filename)
    if not ext:
        return "无法识别文件扩展名"
    if ext.lower() in DANGEROUS_EXTENSIONS:
        return f"禁止下载可执行类型: {ext}"
    if ext.lower() not in ALLOWED_EXTENSIONS:
        return f"不支持的文件类型: {ext}"
    if SUSPICIOUS_DOUBLE_EXT.search(filename):
        return f"可疑双重扩展名: {filename}"
    return None


def _check_content_type(filename: str, content_type: str) -> str | None:
    if not content_type:
        return None
    ct_lower = content_type.split(';')[0].strip().lower()
    if ct_lower in HARMFUL_MIME_TYPES:
        return f"拒绝可执行Content-Type: {ct_lower}"
    for ext in COMPOUND_EXTENSIONS:
        if filename.lower().endswith(ext):
            return None
    _, ext = os.path.splitext(filename)
    expected = EXT_CONTENT_TYPE_MAP.get(ext.lower())
    if expected and ct_lower != expected:
        is_zip_ok = ct_lower in ('application/zip', 'application/x-zip-compressed') and ext.lower() in ('.docx', '.xlsx')
        if not is_zip_ok:
            return f"Content-Type不匹配: 期望{expected}, 实际{ct_lower}"
    return None


def _check_magic_bytes(filepath: str, filename: str) -> str | None:
    for ext in COMPOUND_EXTENSIONS:
        if filename.lower().endswith(ext):
            return None
    _, ext = os.path.splitext(filename)
    ext_lower = ext.lower()
    try:
        with open(filepath, 'rb') as f:
            header = f.read(8)
    except Exception:
        return "无法读取文件头"
    for magic, exts in MAGIC_BYTES.items():
        if header.startswith(magic):
            if ext_lower in exts or (ext_lower in ('.docx', '.xlsx') and '.zip' in exts):
                return None
            return f"文件头与扩展名不匹配"
    if header.startswith(b'MZ') or header.startswith(b'\x7fELF'):
        return "拒绝：检测到可执行文件签名"
    return None


def _scan_text_content(filepath: str, ext_lower: str) -> str | None:
    try:
        with open(filepath, 'rb') as f:
            content = f.read(1 * 1024 * 1024)
    except Exception:
        return "无法读取文件进行扫描"
    if ext_lower in ('.txt', '.csv'):
        scan_size = min(len(content), 10 * 1024 * 1024)
        chunk = content[:scan_size]
        for pattern, label in _TEXT_MALWARE_PATTERNS:
            if pattern.search(chunk):
                return f"检测到恶意代码: {label}"
        b64_matches = _BASE64_PAYLOAD_RE.findall(chunk)
        total_b64 = sum(len(m) for m in b64_matches)
        if total_b64 > 200:
            return "大量Base64编码内容，疑似混淆载荷"
    return None


def _scan_archive(filepath: str, ext_lower: str) -> str | None:
    if ext_lower == '.zip':
        try:
            with zipfile.ZipFile(filepath, 'r') as zf:
                for member in zf.namelist():
                    ml = member.lower()
                    if '..' in member or member.startswith('/'):
                        return f"压缩包含路径遍历: {member}"
                    _, mem_ext = os.path.splitext(member)
                    if mem_ext.lower() in DANGEROUS_EXTENSIONS:
                        return f"压缩包含危险文件: {member}"
        except zipfile.BadZipFile:
            return "非标准ZIP格式"
        except Exception as e:
            return f"压缩包扫描异常: {e}"
    elif ext_lower == '.tar':
        try:
            with tarfile.open(filepath, 'r') as tf:
                for member in tf.getmembers():
                    if member.issym() or member.islnk():
                        return f"压缩包含符号链接: {member.name}"
                    if '..' in member.name or member.name.startswith('/'):
                        return f"压缩包含路径遍历: {member.name}"
        except Exception as e:
            return f"压缩包扫描异常: {e}"
    return None


def _scan_pdf(filepath: str) -> str | None:
    try:
        with open(filepath, 'rb') as f:
            content = f.read(10 * 1024 * 1024)
    except Exception:
        return "无法读取PDF"
    for keyword, label in _PDF_DANGEROUS_KEYS:
        if keyword in content:
            return f"PDF安全风险: {label}"
    return None


def _scan_office(filepath: str) -> str | None:
    try:
        with zipfile.ZipFile(filepath, 'r') as zf:
            names_lower = {n.lower() for n in zf.namelist()}
            for m in _OFFICE_MACRO_MEMBERS:
                if m in names_lower:
                    return f"Office文档含宏代码: {m}"
    except Exception as e:
        return f"Office扫描异常: {e}"
    return None


def _scan_for_malware(filepath: str, filename: str) -> str | None:
    lower = filename.lower()
    for ext in COMPOUND_EXTENSIONS:
        if lower.endswith(ext):
            _, ext = os.path.splitext(lower)
    else:
        _, ext = os.path.splitext(filename)
    ext_lower = ext.lower()
    errors = []
    err = _scan_text_content(filepath, ext_lower)
    if err:
        errors.append(err)
    if ext_lower in ('.zip', '.tar', '.tar.gz', '.tgz', '.gz', '.7z'):
        err = _scan_archive(filepath, ext_lower)
        if err:
            errors.append(err)
    elif ext_lower == '.pdf':
        err = _scan_pdf(filepath)
        if err:
            errors.append(err)
    elif ext_lower in ('.docx', '.xlsx'):
        err = _scan_office(filepath)
        if err:
            errors.append(err)
    if errors:
        return "; ".join(errors)
    return None


def _safe_filename(url: str, content_type: str = None) -> str:
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
    ext_map = {
        'application/pdf': '.pdf', 'image/png': '.png',
        'image/jpeg': '.jpg', 'image/gif': '.gif',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
        'text/plain': '.txt', 'text/csv': '.csv', 'application/zip': '.zip',
        'application/gzip': '.tar.gz', 'application/x-tar': '.tar',
    }
    if content_type:
        ext = ext_map.get(content_type.split(';')[0].strip())
        if ext:
            return f"downloaded_file{ext}"
    return None


def _download_file(url: str, save_dir: str) -> dict:
    import typer
    with httpx.Client(follow_redirects=True, timeout=DEFAULT_TIMEOUT) as client:
        error = _check_url_safety(url)
        if error:
            return {"success": False, "error": error}
        try:
            head = client.head(url)
            content_type = head.headers.get('content-type', '')
            content_length = head.headers.get('content-length')
            final_url = str(head.url)
        except Exception:
            content_type = ''
            content_length = None
            final_url = url
        filename = _safe_filename(final_url, content_type)
        if not filename:
            return {"success": False, "error": f"无法识别文件类型"}
        error = _check_filename(filename)
        if error:
            return {"success": False, "error": error}
        error = _check_content_type(filename, content_type)
        if error:
            return {"success": False, "error": error}
        if content_length and int(content_length) > MAX_FILE_SIZE:
            return {"success": False, "error": "文件过大"}
        total = int(content_length) if content_length else None
        save_path = Path(save_dir) / filename
        save_path.parent.mkdir(parents=True, exist_ok=True)
        initial_size_limit = MAX_FILE_SIZE + 8192
        chunks_buffer = bytearray()
        with client.stream("GET", url) as response:
            response.raise_for_status()
            downloaded = 0
            with open(save_path, 'wb') as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    chunks_buffer.extend(chunk[:4096])
                    if downloaded <= 65536:
                        for pattern, label in _TEXT_MALWARE_PATTERNS[:12]:
                            if pattern.search(bytes(chunks_buffer[-32768:])):
                                f.close()
                                os.remove(save_path)
                                return {"success": False, "error": f"流式扫描检测到恶意代码: {label}"}
                    if downloaded > initial_size_limit:
                        f.close()
                        os.remove(save_path)
                        return {"success": False, "error": "文件过大，已中断"}
        magic_err = _check_magic_bytes(str(save_path), filename)
        if magic_err:
            os.remove(save_path)
            return {"success": False, "error": f"文件头校验: {magic_err}"}
        malware_err = _scan_for_malware(str(save_path), filename)
        if malware_err:
            os.remove(save_path)
            return {"success": False, "error": f"恶意代码扫描: {malware_err}"}
        typer.echo(typer.style("[Success]下载完成，安全检查通过", fg=typer.colors.GREEN))
        return {
            "success": True, "filename": filename,
            "save_path": str(save_path.absolute()), "size": downloaded,
            "content_type": response.headers.get('content-type', content_type),
        }


def download_file(url: str, save_dir: str = "", timeout: int = 600) -> str:
    if not save_dir:
        save_dir = str(DEFAULT_DOWNLOAD_DIR)
    save_dir = os.path.abspath(save_dir)
    error = _check_save_dir(save_dir)
    if error:
        return json.dumps(
            {
                "success": False,
                "error": error
            },
            ensure_ascii=False
        )
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_download_file, url, save_dir)
            result = future.result(timeout=timeout)
        return json.dumps(
            result,
            ensure_ascii=False
        )
    except FutureTimeoutError:
        return json.dumps(
            {
                "success": False,
                "error": "下载超时"
            },
            ensure_ascii=False
        )
    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "error": str(e)
            },
            ensure_ascii=False
        )


DOWNLOAD_FILE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "download_file",
        "description": "下载网络文件到本地。内置三层安全检查：URL SSRF防护、流式恶意代码扫描、文件头魔数校验。支持 pdf/png/jpg/gif/docx/xlsx/txt/csv/zip/tar/gz/7z。【此工具需要用户确认后方可执行】",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "文件下载直链"},
                "save_dir": {"type": "string", "description": "保存目录绝对路径，默认~/下载/"},
                "timeout": {"type": "integer", "description": "超时(秒)，默认600"},
            },
            "required": ["url"],
        },
    },
}
