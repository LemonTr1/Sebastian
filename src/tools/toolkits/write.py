from pathlib import Path
import json
from src.tools.tools_registry import get_tools_registry

SENSITIVE_FILES = [
    # Shell 和环境配置
    ".bash_history",
    ".bash_logout",
    ".bashrc",
    ".profile",
    ".zshrc",
    ".zprofile",
    ".zlogin",
    ".zlogout",
    ".zsh_history",
    ".zcompdump",
    ".zcompcache",
    ".zcompletions",
    ".zdump",
    ".zshenv",

    # SSH 相关
    ".ssh/authorized_keys",
    ".ssh/known_hosts",
    ".ssh/config",
    ".ssh/id_rsa",
    ".ssh/id_rsa.pub",
    ".ssh/id_ed25519",
    ".ssh/id_ed25519.pub",
    ".ssh/id_ecdsa",
    ".ssh/id_ecdsa.pub",
    ".ssh/id_dsa",
    ".ssh/id_dsa.pub",

    # GPG/PGP 密钥
    ".gnupg/gpg.conf",
    ".gnupg/pubring.kbx",
    ".gnupg/pubring.gpg",
    ".gnupg/secring.gpg",
    ".gnupg/trustdb.gpg",
    ".gnupg/random_seed",
    ".gnupg/dirmngr.conf",
    ".gnupg/gnupg_spawn_keyboxd_sentinel",

    # Git 相关
    ".gitconfig",
    ".gitignore_global",
    ".git-credentials",
    ".gitconfig.local",

    # 认证和密钥
    ".netrc",
    ".authinfo",
    ".authinfo.gpg",
    ".kube/config",
    ".aws/credentials",
    ".aws/config",
    ".aws/cli/cache",

    # Docker 配置
    ".docker/config.json",

    # 密码存储
    ".local/share/keyrings/",
    ".local/share/kwalletd/",
    ".local/share/gnome-keyring/",

    # 浏览器敏感数据
    ".config/google-chrome/",
    ".config/chromium/",
    ".config/mozilla/",
    ".mozilla/firefox/",
    ".config/safari/",

    # 应用令牌和密钥
    ".local/share/application-registry/",
    ".local/share/applications/",
    ".config/helix/config.toml",
    ".config/nvim/",
    ".config/vim/",
    ".viminfo",
    ".vimrc",

    # 系统级用户配置
    ".Xauthority",
    ".ICEauthority",
    ".xsession-errors",
    ".xsession-errors.old",

    # 密码和令牌存储
    ".local/share/tokens/",
    ".local/share/secrets/",
    ".local/share/password-store/",

    # 邮件客户端配置
    ".muttrc",
    ".mutt/cache/",
    ".mailcap",

    # 终端 multiplexer 配置
    ".tmux.conf",
    ".screenrc",

    # 密码管理器
    ".local/share/pass/",
    ".local/share/bitwarden/",
    ".local/share/keepassxc/",

    # 程序员工具
    ".local/share/nvim/",
    ".local/share/vim/",
    ".local/share/helix/",
    ".local/share/zsh/",
    ".local/share/bash/",

    # IDE 和编辑器配置
    ".vscode/",
    ".jetbrains/",
    ".idea/",
    ".vim/",
    ".emacs.d/",
    ".emacs",
    ".spacemacs",
    ".doom.d/",

    # 云存储配置
    ".dropbox/",
    ".dropbox-dist/",
    ".config/onedrive/",
    ".config/google-drive-ocamlfuse/",

    # VPN 和网络配置
    ".config/openvpn/",
    ".config/wireguard/",
    ".config/nmcli/",

    # 加密货币钱包
    ".bitcoin/",
    ".ethereum/keystore/",
    ".config/Monero/",
    ".local/share/atomic/",

    # 数据库凭证
    ".my.cnf",
    ".pgpass",
    ".mongorc.js",

    # 云服务 CLI 凭证
    ".config/gcloud/",
    ".azure/",
    ".config/az/",
    ".config/azure/",

    # 版本控制系统缓存
    ".svn/",
    ".hg/",
    ".bzr/",

    # 密钥和证书存储
    ".local/share/pki/",
    ".config/pki/",

    # 其他敏感配置
    ".config/nextcloud/",
    ".config/syncthing/",
    ".config/protonvpn/",
    ".config/nordvpn/",
    ".config/expressvpn/",
    ".local/share/Steam/",
    ".steam/",

    # SSH agent socket
    ".ssh/agent.sock",

    # Gnome Keyring
    ".local/share/keyrings/",

    # Session 和锁文件
    ".X0-lock",
    ".Xauthority",
    ".local/share/sessions/",

    # Systemd 用户服务
    ".config/systemd/user/",
    ".local/share/systemd/user/",

    # Wayland 配置
    ".wayland-sock",

    # 日志文件
    ".local/share/logs/",
    ".cache/logs/",

    # 备份和版本历史
    ".local/share/Trash/",
    ".local/share/recently-used.xbel",
]

def write(file_path: str, content: str) -> str:
    if file_path.endswith(".pdf") or file_path.endswith(".docx"):
        return json.dumps(
            {
                "success": False,
                "error": "不支持写PDF文件或docx文件"
            },
            ensure_ascii=False
        )
    try:
        file_path = str(Path(file_path).expanduser().resolve())
        if not Path(file_path).is_relative_to(Path.home()):
            return json.dumps({
                "success": False,
                "error": "只能在用户家目录下执行写操作"
            }, ensure_ascii=False)

        if file_path in [str(Path.home() / deny) for deny in SENSITIVE_FILES]:
            return json.dumps({
                "success": False,
                "error": f"{file_path}为敏感文件，禁止写入"
            }, ensure_ascii=False)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return json.dumps(
            {
                "success": True,
                "summary": f"文件 {file_path} 内容已写入成功"
            },
            ensure_ascii=False
        )
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
        "description": "将提供的内容写入文件。如果文件不存在，则创建它。如果已存在，则替换其先前的全部内容。【此工具需要用户确认后方可执行】",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "目标文件的绝对路径，如 /home/user/test.txt"},
                "content": {"type": "string", "description": "要写入的内容（完全替换）"},
            },
            "required": ["file_path", "content"],
        },
    },
}

get_tools_registry().register_tool("write", write, WRITE_SCHEMA, hitl=True, for_agent="Brain_Agent")
