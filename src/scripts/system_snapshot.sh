: "
name: system_snapshot
description: Collects and outputs system information in JSON format.
parameters: None
"
echo "{"
echo "  \"os\": \"$(cat /etc/os-release | grep '^NAME=' | cut -d= -f2 | tr -d '\"')\","
echo "  \"version\": \"$(uname -r)\","
echo "  \"arch\": \"$(uname -m)\","
echo "  \"hostname\": \"$(hostname)\","
echo "  \"uptime\": \"$(uptime -p 2>/dev/null || uptime | awk '{print $3,$4}')\","
echo "  \"cpu_cores\": $(nproc),"
echo "  \"memory_mb\": $(free -m | awk '/Mem/{print $2}'),"
echo "  \"disk_gb\": $(df -BG / | awk 'NR==2{print $2}' | tr -d 'G'),"
echo "  \"ip\": \"$(hostname -I | awk '{print $1}')\","
echo "  \"user\": \"$(whoami)\","
echo "  \"shell\": \"$SHELL\""
echo "}"