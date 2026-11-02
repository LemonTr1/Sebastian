#!/usr/bin/env bash
# Sebastian 一键安装脚本：检测/安装 uv 与 bubblewrap，创建虚拟环境并安装项目。
#
# 用法：
#   ./install.sh
#   ./install.sh --python 3.12
#   ./install.sh --skip-bwrap
#   ./install.sh --dry-run
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${SEBASTIAN_VENV:-$ROOT_DIR/.venv}"
BIN_DIR="${SEBASTIAN_BIN_DIR:-$HOME/.local/bin}"
PYTHON_VERSION="3.11"
SKIP_BWRAP=0
DRY_RUN=0
UV=""

usage() {
    cat <<'EOF'
用法: ./install.sh [选项]

选项:
  --python VERSION   指定 Python 版本（默认 3.11）
  --venv DIR         指定虚拟环境目录（默认 .venv）
  --skip-bwrap       不尝试安装 bubblewrap（只检测并提示）
  --dry-run          只打印将要执行的操作，不修改系统
  -h, --help         显示帮助

环境变量:
  SEBASTIAN_VENV     虚拟环境目录（默认 .venv）
  SEBASTIAN_BIN_DIR  启动器目录（默认 ~/.local/bin）
EOF
}

log()  { printf '\033[1;32m[install]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }
err()  { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; }
die()  { err "$*"; exit 1; }

is_root() {
    [ "${EUID:-$(id -u)}" -eq 0 ]
}

have_sudo() {
    command -v sudo >/dev/null 2>&1
}

as_root() {
    if is_root; then
        "$@"
    elif have_sudo; then
        sudo "$@"
    else
        return 1
    fi
}

find_uv() {
    if command -v uv >/dev/null 2>&1; then
        command -v uv
        return 0
    fi
    for path in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv"; do
        if [ -x "$path" ]; then
            printf '%s\n' "$path"
            return 0
        fi
    done
    return 1
}

install_uv() {
    if UV="$(find_uv)"; then
        log "uv 已安装：$UV ($("$UV" --version 2>/dev/null || true))"
        return
    fi

    log "未检测到 uv，准备使用官方安装脚本"
    if (( DRY_RUN )); then
        printf '  [dry-run] 下载并执行 https://astral.sh/uv/install.sh\n'
        return
    fi

    if ! command -v curl >/dev/null 2>&1 && ! command -v wget >/dev/null 2>&1; then
        die "需要 curl 或 wget 下载 uv"
    fi

    tmp="$(mktemp)"
    if command -v curl >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh -o "$tmp" || {
            rm -f "$tmp"
            die "下载 uv 安装脚本失败"
        }
    else
        wget -qO "$tmp" https://astral.sh/uv/install.sh || {
            rm -f "$tmp"
            die "下载 uv 安装脚本失败"
        }
    fi
    sh "$tmp" || {
        rm -f "$tmp"
        die "uv 安装脚本执行失败"
    }
    rm -f "$tmp"

    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    if ! UV="$(find_uv)"; then
        die "uv 安装后仍未找到；请把 ~/.local/bin（或 ~/.cargo/bin）加入 PATH 后重试"
    fi
    log "uv 已安装：$UV ($("$UV" --version 2>/dev/null || true))"
}

check_bwrap() {
    command -v bwrap >/dev/null 2>&1
}

bwrap_works() {
    # 只做最小命名空间自检；失败通常是用 userns/AppArmor 限制
    bwrap --ro-bind / / --dev /dev true >/dev/null 2>&1
}

install_bwrap() {
    if check_bwrap; then
        log "bubblewrap 已安装：$(bwrap --version 2>/dev/null || true)"
        if ! bwrap_works; then
            warn "bwrap 存在，但最小命名空间自检失败（可能被 userns/AppArmor 限制）"
        fi
        return
    fi

    warn "未检测到 bubblewrap"
    if (( SKIP_BWRAP )); then
        warn "--skip-bwrap：跳过安装；bash 沙箱将不可用"
        return
    fi

    if (( DRY_RUN )); then
        printf '  [dry-run] 使用系统包管理器安装 bubblewrap\n'
        return
    fi

    if ! is_root && ! have_sudo; then
        warn "没有 root/sudo，跳过 bubblewrap 安装"
        warn "请手动安装：https://github.com/containers/bubblewrap"
        return
    fi

    if command -v apt-get >/dev/null 2>&1; then
        if ! as_root apt-get update; then
            warn "apt-get update 失败，尝试直接安装"
        fi
        as_root apt-get install -y bubblewrap || {
            warn "apt 安装 bubblewrap 失败，请手动安装"
            return
        }
    elif command -v dnf >/dev/null 2>&1; then
        as_root dnf install -y bubblewrap || { warn "dnf 安装失败"; return; }
    elif command -v pacman >/dev/null 2>&1; then
        as_root pacman -S --needed --noconfirm bubblewrap || { warn "pacman 安装失败"; return; }
    elif command -v zypper >/dev/null 2>&1; then
        as_root zypper install -y bubblewrap || { warn "zypper 安装失败"; return; }
    elif command -v apk >/dev/null 2>&1; then
        as_root apk add --no-cache bubblewrap || { warn "apk 安装失败"; return; }
    else
        warn "未识别的包管理器；请手动安装 bubblewrap"
        warn "参考：https://github.com/containers/bubblewrap"
        return
    fi

    if check_bwrap; then
        log "bubblewrap 已安装：$(bwrap --version 2>/dev/null || true)"
        if ! bwrap_works; then
            warn "bwrap 最小命名空间自检失败（可能被 userns/AppArmor 限制）"
        fi
    else
        warn "安装命令已执行，但仍未找到 bwrap；请检查系统包管理器"
    fi
}

setup_venv() {
    log "准备虚拟环境：$VENV（目标 Python $PYTHON_VERSION，已有则复用）"
    if (( DRY_RUN )); then
        printf '  [dry-run] uv python install %s\n' "$PYTHON_VERSION"
        printf '  [dry-run] uv venv --python %s %s\n' "$PYTHON_VERSION" "$VENV"
        printf '  [dry-run] uv pip install --python %s/bin/python -e %s\n' "$VENV" "$ROOT_DIR"
        return
    fi

    if [ -d "$VENV" ]; then
        mismatch="$(find "$VENV" ! -user "$(id -u)" -print -quit 2>/dev/null || true)"
        if [ -n "$mismatch" ]; then
            warn "现有虚拟环境含非当前用户文件：$mismatch"
            if as_root chown -R "$(id -u):$(id -g)" "$VENV"; then
                log "已修复虚拟环境所有权"
            else
                backup="${VENV}.bak.$(date +%Y%m%d-%H%M%S)"
                warn "无法修复所有权，旧环境将移到：$backup"
                if ! mv "$VENV" "$backup"; then
                    die "无法移动旧虚拟环境；请手动执行 sudo chown -R \"$(id -u):$(id -g)\" \"$VENV\" 后重试"
                fi
                warn "旧环境未删除；清理：sudo rm -rf \"$backup\""
            fi
        fi
    fi

    if [ ! -x "$VENV/bin/python" ]; then
        # uv 可以下载受管 Python；失败时继续用系统已有版本尝试
        "$UV" python install "$PYTHON_VERSION" >/dev/null 2>&1 || true
        "$UV" venv --python "$PYTHON_VERSION" "$VENV"
    else
        log "复用已有虚拟环境：$("$VENV/bin/python" --version 2>&1)"
    fi

    "$UV" pip install --python "$VENV/bin/python" -e "$ROOT_DIR"
    "$VENV/bin/python" -c "import typer, openai, prompt_toolkit, src; print('依赖导入正常')"
}

install_launcher() {
    launcher="$BIN_DIR/sebastian"
    log "创建可直接运行的命令：$launcher"
    if (( DRY_RUN )); then
        printf '  [dry-run] 写入启动器 %s -> %s\n' "$launcher" "$VENV/bin/sebastian"
        return
    fi
    if [ ! -x "$VENV/bin/sebastian" ]; then
        die "未找到 $VENV/bin/sebastian，安装可能失败"
    fi

    existing="$(command -v sebastian 2>/dev/null || true)"
    if [ -n "$existing" ] && [ "$existing" != "$launcher" ]; then
        warn "PATH 中已有另一个 sebastian：$existing；新命令会写入 $launcher"
    fi

    if ! mkdir -p "$BIN_DIR"; then
        warn "无法创建 $BIN_DIR；跳过启动器，仍可使用 $VENV/bin/sebastian"
        return
    fi
    if ! printf '#!/usr/bin/env sh\n# Generated by Sebastian install.sh; re-run to refresh.\nexec "%s" "$@"\n' "$VENV/bin/sebastian" > "$launcher"; then
        warn "写入 $launcher 失败；仍可使用 $VENV/bin/sebastian"
        return
    fi
    chmod +x "$launcher"
    log "已创建：$launcher"

    case ":$PATH:" in
        *":$BIN_DIR:"*) ;;
        *)
            warn "$BIN_DIR 不在当前 PATH；一次性加入：export PATH=\"$BIN_DIR:\$PATH\""
            ;;
    esac
}

main() {
    while [ $# -gt 0 ]; do
        case "$1" in
            --python)
                [ $# -ge 2 ] || die "--python 需要版本号"
                PYTHON_VERSION="$2"
                shift 2
                ;;
            --venv)
                [ $# -ge 2 ] || die "--venv 需要目录"
                VENV="$2"
                shift 2
                ;;
            --skip-bwrap)
                SKIP_BWRAP=1
                shift
                ;;
            --dry-run)
                DRY_RUN=1
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                usage
                die "未知选项：$1"
                ;;
        esac
    done

    cd "$ROOT_DIR"
    log "项目目录：$ROOT_DIR"
    install_uv
    install_bwrap
    setup_venv
    install_launcher

    echo
    if (( DRY_RUN )); then
        log "dry-run 完成，未修改系统"
        return
    fi
    log "安装完成（无需激活虚拟环境）"
    cat <<EOF
  配置 API Key: sebastian setup
  启动:         sebastian
  直接路径:     "$VENV/bin/sebastian"
  可选激活:     source "$VENV/bin/activate"
EOF
    echo
    if ! check_bwrap; then
        warn "bubblewrap 仍未安装：bash 沙箱不可用"
    elif ! bwrap_works; then
        warn "bwrap 自检失败：请检查内核 unprivileged userns / AppArmor 限制"
    fi
    if ! command -v uv >/dev/null 2>&1; then
        warn "uv 不在当前 PATH；请把 ~/.local/bin（或 ~/.cargo/bin）加入 shell 配置"
    fi
}

main "$@"
