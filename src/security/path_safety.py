import os
from pathlib import Path
from src.utils.exceptions import SecurityException


def resolve_safe_path(path: str, path_type: str = "abs") -> str:
    abs_path = os.path.abspath(path).strip()
    real_path = os.path.realpath(path).strip()

    if not os.path.exists(real_path):
        raise SecurityException(
            f"路径不存在（或符号链接指向不存在目标）：{real_path}"
        )

    home_dir = Path.home()
    if not Path(real_path).is_relative_to(home_dir) or not Path(abs_path).is_relative_to(home_dir):
        raise SecurityException(f"路径位于用户家目录外，严禁访问：{home_dir}")

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

    relative_sensitive_dirs = {
        '.ssh', '.gnupg', '.aws', '.docker', '.kube',
        '.mozilla', '.thunderbird', '.config', '.npm', '.cache'
    }
    for part in real_path_obj.parts:
        if part in relative_sensitive_dirs:
            raise SecurityException(
                f"路径包含敏感目录分量，严禁访问：'{part}'（完整路径：{real_path}）"
            )

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

    if real_path_obj.suffix.lower() in {'.pem', '.key', '.p12', '.pfx', '.cer', '.crt', '.pub'}:
        raise SecurityException(f"路径具有敏感扩展名，严禁访问（完整路径：{real_path}）")

    lower_name = file_name.lower()
    if any(kw in lower_name for kw in ('secret', 'token', 'password', 'credential', 'api_key', 'private_key')):
        raise SecurityException(f"路径文件名包含敏感关键词，严禁访问（完整路径：{real_path}）")

    if path_type != "abs":
        return real_path

    return abs_path
