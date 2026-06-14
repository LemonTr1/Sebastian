: "
name: http_req
description: 发送HTTP请求
parameters: $1=HTTP方法(default: GET), $2=URL, $3=请求数据(仅POST方法有效)
"
METHOD="${1:-GET}"
URL="$2"
DATA="${3:-}"

if command -v curl >/dev/null; then
    if [ "$METHOD" = "POST" ] && [ -n "$DATA" ]; then
        curl -s -X POST -H "Content-Type: application/json" -d "$DATA" "$URL"
    else
        curl -s -X "$METHOD" "$URL"
    fi
elif command -v wget >/dev/null; then
    if [ "$METHOD" = "POST" ] && [ -n "$DATA" ]; then
        wget -qO- --post-data="$DATA" --header="Content-Type: application/json" "$URL"
    else
        wget -qO- "$URL"
    fi
else
    echo "{\"error\":\"缺少 curl 或 wget\"}" >&2
    exit 1
fi