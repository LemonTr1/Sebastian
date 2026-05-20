import os
from pathlib import Path
from src.Interfaces.Exception.SecurityException import SecurityException


#同时递归解析符号链接，判断符号链接指向的源文件是否存在，是否在家目录外，是否涉及敏感文件或目录，一个不满足就SecurityException

def resolve_safe_path(path: str, type: str = "abs") -> str:
    """
    将路径转为绝对路径，递归解析符号链接到最终目标，
    通过安全检查后根据选择返回真实绝对路径还是绝对路径，默认返回非真实的绝对路径。
    """
    # 1. 绝对路径 + 递归穿透符号链接
    abs_path = os.path.abspath(path).strip()
    real_path = os.path.realpath(path).strip()

    # 2. 存在性检查（realpath 对死链也会返回路径，必须显式检查）
    if not os.path.exists(real_path):
        raise SecurityException(
            f"路径不存在（或符号链接指向不存在目标）：{real_path}"
        )

    # 3. 家目录检查（两者必须同时在家目录内）
    home_dir = Path.home()
    if not Path(real_path).is_relative_to(home_dir) or not Path(abs_path).is_relative_to(home_dir):
        raise SecurityException(f"路径位于用户家目录外，严禁访问：{home_dir}")

    # 4. 敏感目录检查
    # 绝对路径类敏感目录（要求路径以该目录为根前缀）
    absolute_sensitive_dirs = [
        '/etc', '/boot', '/root', '/sys', '/proc', '/dev',
        '/run', '/tmp', '/var',
    ]
    real_path_obj = Path(real_path)
    for sd in absolute_sensitive_dirs:
        sd_path = Path(sd).resolve()
        try:
            real_path_obj.relative_to(sd_path)
            raise SecurityException(
                f"路径位于敏感目录下，严禁访问：{sd}（完整路径：{real_path}）"
            )
        except ValueError:
            pass

    # 相对名类敏感目录（路径中任何一级目录名匹配即触发）
    relative_sensitive_dirs = {
        '.ssh', '.gnupg', '.aws', '.docker', '.kube',
        '.mozilla', '.thunderbird', '.config',
    }
    for part in real_path_obj.parts:
        if part in relative_sensitive_dirs:
            raise SecurityException(
                f"路径包含敏感目录分量，严禁访问：'{part}'（完整路径：{real_path}）"
            )

    # 5. 敏感文件名检查（匹配文件名，而非完整路径）
    sensitive_names = {
        '.bashrc', '.bash_profile', '.zshrc', '.profile', '.zshenv', '.zprofile',
        'id_rsa', 'id_ed25519', 'id_ecdsa', 'id_dsa',
        '.netrc', '.pgpass', '.my.cnf', '.npmrc', '.pypirc', '.git-credentials',
        '.bash_history', '.zsh_history', '.python_history',
        '.env', '.env.local', '.env.production',
        'credentials', 'token', 'secret',
    }
    file_name = real_path_obj.name
    if file_name in sensitive_names:
        raise SecurityException(
            f"路径为敏感文件，严禁访问：{file_name}（完整路径：{real_path}）"
        )

    # 6. 敏感扩展名检查
    if real_path_obj.suffix.lower() in {'.pem', '.key', '.p12', '.pfx', '.cer', '.crt', '.pub'}:
        raise SecurityException(f"路径具有敏感扩展名，严禁访问（完整路径：{real_path}）")

    # 7. 敏感关键词检查
    lower_name = file_name.lower()
    if any(kw in lower_name for kw in ('secret', 'token', 'password', 'credential', 'api_key', 'private_key')):
        raise SecurityException(f"路径文件名包含敏感关键词，严禁访问（完整路径：{real_path}）")

    if type != "abs":
        return real_path

    return abs_path