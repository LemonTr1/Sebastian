: "
name: process_ctl
description: Manages processes by listing, checking, or killing them based on name or PID.
parameters: $1=操作类型(list|check|kill), $2=目标进程名或PID
"
ACTION="${1:-list}"
TARGET="${2:-}"

case "$ACTION" in
    list)
        ps aux | awk 'NR==1 || /'"$TARGET"'/ && !/awk/' | \
        while read user pid cpu mem vsz rss tty stat start time command; do
            [ "$pid" = "PID" ] && continue
            echo "{\"pid\":$pid,\"user\":\"$user\",\"cpu\":\"$cpu\",\"mem\":\"$mem\",\"command\":\"$command\"}"
        done
        ;;
    check)
        if pgrep -x "$TARGET" > /dev/null; then
            pid=$(pgrep -x "$TARGET" | head -1)
            echo "{\"running\":true,\"pid\":$pid}"
        else
            echo "{\"running\":false}"
        fi
        ;;
    kill)
        if [ -z "$TARGET" ]; then
            echo "{\"error\":\"缺少进程名或PID\"}" >&2
            exit 1
        fi
        if kill "$TARGET" 2>/dev/null || pkill -x "$TARGET" 2>/dev/null; then
            echo "{\"killed\":true,\"target\":\"$TARGET\"}"
        else
            echo "{\"killed\":false,\"error\":\"无法终止\"}" >&2
            exit 1
        fi
        ;;
    *)
        echo "{\"error\":\"未知操作: $ACTION\"}" >&2
        exit 1
        ;;
esac