: "
name: project_tree
description: Generates a JSON representation of the directory structure for a given path and depth.
parameters: $1=目录路径, $2=最大层级(default: 3)
"
DIR="${1:-.}"
DEPTH="${2:-3}"

echo "{\"tree\": ["
first=1
find "$DIR" -maxdepth "$DEPTH" -not -path '*/\.*' -not -path '*/node_modules/*' | sort | while read path; do
    level=$(echo "$path" | tr -cd '/' | wc -c)
    indent=$((level * 2))
    name=$(basename "$path")
    [ -d "$path" ] && type="dir" || type="file"
    [ $first -eq 1 ] && first=0 || echo ","
    printf "{\"name\":\"%s\",\"type\":\"%s\",\"depth\":%d}" "$name" "$type" "$level"
done
echo ""
echo "]}"