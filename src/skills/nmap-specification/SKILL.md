---
name: Nmap网络扫描工具
description: Nmap网络扫描工具使用说明书。
---
# Nmap 网络扫描工具使用说明书

## 概述

Nmap（Network Mapper）是开源的网络扫描与安全审计工具，用于发现主机、开放端口、运行服务、操作系统类型及潜在漏洞。它是网络侦察阶段的核心工具。

**核心功能：**
- 主机发现（Host Discovery）
- 端口扫描（Port Scanning）
- 服务与版本探测（Service/Version Detection）
- 操作系统探测（OS Detection）
- 脚本扫描（NSE - Nmap Scripting Engine）

**注意：** 仅对授权范围内的网络进行扫描。未经授权的扫描可能违反法律法规。

---

## 1. 目标指定（Target Specification）

定义扫描对象的基本方式：

| 命令示例 | 说明 |
|---------|------|
| `nmap 192.168.1.1` | 扫描单个IP |
| `nmap 192.168.1.1 10.0.0.1` | 扫描多个IP |
| `nmap 192.168.1.1-254` | 扫描IP范围 |
| `nmap 192.168.1.0/24` | CIDR子网扫描 |
| `nmap scanme.nmap.org` | 扫描域名 |
| `nmap -iL targets.txt` | 从文件导入目标列表（每行一个） |
| `nmap -iR 100` | 随机扫描100个主机 |
| `nmap 192.168.1.0/24 --exclude 192.168.1.1` | 排除特定主机 |
| `nmap 192.168.1.0/24 --excludefile exclude.txt` | 从文件排除主机 |

---

## 2. 主机发现（Host Discovery）

探测网络中存活的主机，不进行端口扫描：

| 参数 | 命令示例 | 说明 |
|------|---------|------|
| `-sn` | `nmap -sn 192.168.1.0/24` | Ping扫描，仅主机发现，不扫端口 |
| `-Pn` | `nmap -Pn 192.168.1.1` | 跳过主机发现，视所有目标为在线 |
| `-PS` | `nmap -PS22,80,443 192.168.1.0/24` | TCP SYN探测（可指定端口） |
| `-PA` | `nmap -PA80,443 192.168.1.0/24` | TCP ACK探测 |
| `-PU` | `nmap -PU53,161 192.168.1.0/24` | UDP探测 |
| `-PR` | `sudo nmap -PR -sn 192.168.1.0/24` | ARP探测（局域网最快，需root） |
| `-PE` | `nmap -PE 192.168.1.0/24` | ICMP Echo探测 |
| `-n` | `nmap -n 192.168.1.0/24` | 禁用DNS解析，加速扫描 |
| `-R` | `nmap -R 192.168.1.0/24` | 始终进行反向DNS解析 |
| `-sL` | `nmap -sL 192.168.1.0/24` | 仅列出目标，不扫描 |

**提示：** 生产环境服务器常屏蔽ICMP，建议用 `-Pn` 或 `-PS` 替代单纯ping扫描。

---

## 3. 端口扫描技术（Scan Techniques）

### 3.1 TCP扫描

| 参数 | 命令示例 | 说明 | 权限要求 |
|------|---------|------|---------|
| `-sS` | `sudo nmap -sS 192.168.1.1` | **SYN半开放扫描**（默认推荐），不完成三次握手 | root |
| `-sT` | `nmap -sT 192.168.1.1` | TCP全连接扫描，使用系统connect() | 普通用户 |
| `-sA` | `sudo nmap -sA 192.168.1.1` | ACK扫描，用于探测防火墙规则 | root |
| `-sN` | `sudo nmap -sN 192.168.1.1` | NULL扫描（无标志位） | root |
| `-sF` | `sudo nmap -sF 192.168.1.1` | FIN扫描 | root |
| `-sX` | `sudo nmap -sX 192.168.1.1` | Xmas扫描（FIN+PSH+URG） | root |
| `-sM` | `sudo nmap -sM 192.168.1.1` | Maimon扫描 | root |

### 3.2 UDP扫描

| 参数 | 命令示例 | 说明 |
|------|---------|------|
| `-sU` | `sudo nmap -sU 192.168.1.1` | UDP扫描（速度较慢，建议限制端口范围） |

**UDP扫描优化：**
```bash
# 仅扫描常用UDP端口（加速）
sudo nmap -sU --top-ports 20 192.168.1.1

# 指定UDP端口范围
sudo nmap -sU -p 53,161,500 192.168.1.1

# 提高UDP扫描速率
sudo nmap -sU -p 1-65535 --min-rate 1000 192.168.1.1
```

### 3.3 其他扫描类型

| 参数 | 命令示例 | 说明 |
|------|---------|------|
| `-sO` | `sudo nmap -sO 192.168.1.1` | IP协议扫描 |
| `-sZ` | `sudo nmap -sZ 192.168.1.1` | SCTP COOKIE ECHO扫描 |
| `-sY` | `sudo nmap -sY 192.168.1.1` | SCTP INIT扫描 |
| `-b` | `nmap -b ftp_relay_host 192.168.1.1` | FTP反弹扫描 |

---

## 4. 端口指定（Port Specification）

| 参数 | 命令示例 | 说明 |
|------|---------|------|
| `-p` | `nmap -p 80 192.168.1.1` | 扫描指定端口 |
| `-p` | `nmap -p 22,80,443 192.168.1.1` | 扫描多个端口 |
| `-p` | `nmap -p 1-1000 192.168.1.1` | 扫描端口范围 |
| `-p` | `nmap -p U:53,T:21-25,80 192.168.1.1` | 同时指定TCP和UDP端口 |
| `-p` | `nmap -p http,https,ssh 192.168.1.1` | 按服务名扫描 |
| `-p-` | `nmap -p- 192.168.1.1` | 扫描全部65535个TCP端口 |
| `-F` | `nmap -F 192.168.1.1` | 快速扫描（仅Top 100端口） |
| `--top-ports` | `nmap --top-ports 2000 192.168.1.1` | 扫描Top N个常用端口 |
| `-r` | `nmap -r -p 1-1000 192.168.1.1` | 按顺序扫描端口（非随机） |

---

## 5. 服务与版本探测（Service/Version Detection）

| 参数 | 命令示例 | 说明 |
|------|---------|------|
| `-sV` | `nmap -sV 192.168.1.1` | 探测服务版本信息 |
| `-sV --version-intensity 5` | `nmap -sV --version-intensity 5 192.168.1.1` | 设置探测强度（0-9，默认7） |
| `-sV --version-light` | `nmap -sV --version-light 192.168.1.1` | 轻量探测（强度2） |
| `-sV --version-all` | `nmap -sV --version-all 192.168.1.1` | 尝试所有探测（强度9） |
| `-A` | `nmap -A 192.168.1.1` | 综合扫描（= -sV -sC -O --traceroute） |

---

## 6. 操作系统探测（OS Detection）

| 参数 | 命令示例 | 说明 |
|------|---------|------|
| `-O` | `sudo nmap -O 192.168.1.1` | 启用操作系统探测（需至少一个开放和一个关闭端口） |
| `-O --osscan-limit` | `sudo nmap -O --osscan-limit 192.168.1.1` | 若无开放+关闭端口则跳过OS探测 |
| `-O --osscan-guess` | `sudo nmap -O --osscan-guess 192.168.1.1` | 更激进地猜测OS |
| `-O --max-os-tries 1` | `sudo nmap -O --max-os-tries 1 192.168.1.1` | 设置OS探测重试次数 |
| `-A` | `nmap -A 192.168.1.1` | 包含OS探测的综合扫描 |

---

## 7. NSE脚本扫描（Nmap Scripting Engine）

NSE是Nmap的强大脚本引擎，用于漏洞检测、服务枚举、信息收集等。

### 7.1 脚本调用方式

| 参数 | 命令示例 | 说明 |
|------|---------|------|
| `-sC` | `nmap -sC 192.168.1.1` | 使用默认脚本集合（= --script=default） |
| `--script` | `nmap --script=vuln 192.168.1.1` | 运行指定脚本 |
| `--script` | `nmap --script=http-enum,http-headers 192.168.1.1` | 运行多个脚本 |
| `--script` | `nmap --script="http-*" 192.168.1.1` | 使用通配符批量调用 |
| `--script-args` | `nmap --script=ftp-brute --script-args userdb=users.txt 192.168.1.1` | 传递脚本参数 |
| `--script-updatedb` | `nmap --script-updatedb` | 更新脚本数据库 |

### 7.2 常用脚本分类

| 场景 | 命令示例 |
|------|---------|
| **漏洞扫描** | `nmap --script vuln -sV 192.168.1.1` |
| **Web枚举** | `nmap -p 80,443 --script=http-enum,http-headers,http-methods 192.168.1.1` |
| **SMB枚举** | `nmap -p 445 --script smb-enum-shares,smb-vuln* 192.168.1.1` |
| **SSH信息** | `nmap -p 22 --script ssh-auth-methods,ssh-hostkey 192.168.1.1` |
| **FTP检测** | `nmap -p 21 --script ftp-anon,ftp-bounce 192.168.1.1` |
| **数据库** | `nmap -p 3306,1433,5432 --script mysql-info,ms-sql-info,pgsql-brute 192.168.1.1` |
| **DNS枚举** | `nmap -p 53 --script dns-zone-transfer,dns-brute 192.168.1.1` |
| **SSL/TLS** | `nmap -p 443 --script ssl-heartbleed,ssl-enum-ciphers 192.168.1.1` |
| **全协议暴力破解** | `nmap --script brute 192.168.1.1` |

---

## 8. 时间和性能控制（Timing & Performance）

| 参数 | 命令示例 | 说明 |
|------|---------|------|
| `-T0` | `nmap -T0 192.168.1.1` | 偏执模式（Paranoid），极慢，用于IDS规避 |
| `-T1` | `nmap -T1 192.168.1.1` |  Sneaky模式，慢速 |
| `-T2` | `nmap -T2 192.168.1.1` |  Polite模式，低速率 |
| `-T3` | `nmap -T3 192.168.1.1` |  Normal模式（默认） |
| `-T4` | `nmap -T4 192.168.1.1` |  Aggressive模式，快速（推荐） |
| `-T5` | `nmap -T5 192.168.1.1` |  Insane模式，极快（可能丢包） |
| `--min-rate` | `nmap --min-rate 1000 192.168.1.1` | 设置最小发包速率（包/秒） |
| `--max-rate` | `nmap --max-rate 500 192.168.1.1` | 设置最大发包速率 |
| `--host-timeout` | `nmap --host-timeout 30m 192.168.1.0/24` | 单主机超时时间 |
| `--max-retries` | `nmap --max-retries 2 192.168.1.1` | 设置最大重试次数 |
| `--max-parallelism` | `nmap --max-parallelism 100 192.168.1.1` | 最大并行扫描数 |
| `--min-parallelism` | `nmap --min-parallelism 50 192.168.1.1` | 最小并行扫描数 |

---

## 9. 防火墙/IDS规避与欺骗（Firewall/IDS Evasion）

| 参数 | 命令示例 | 说明 |
|------|---------|------|
| `-f` | `nmap -f 192.168.1.1` | 分片扫描（将IP包分片） |
| `--mtu` | `nmap --mtu 32 192.168.1.1` | 自定义MTU分片大小（必须是8的倍数） |
| `-D` | `nmap -D 192.168.1.101,192.168.1.102,ME 192.168.1.1` | 使用诱饵IP混淆真实源地址（ME=本机） |
| `-S` | `nmap -S 10.0.0.1 -e eth0 -Pn 192.168.1.1` | 伪造源IP地址 |
| `-g` | `nmap -g 53 192.168.1.1` | 指定源端口（如伪装成DNS查询） |
| `--proxies` | `nmap --proxies http://10.0.0.1:8080 192.168.1.1` | 通过HTTP/SOCKS4代理扫描 |
| `--data-length` | `nmap --data-length 200 192.168.1.1` | 在包尾附加随机数据 |
| `--randomize-hosts` | `nmap --randomize-hosts 192.168.1.0/24` | 随机化主机扫描顺序 |
| `--spoof-mac` | `nmap --spoof-mac 0 192.168.1.1` | 伪造MAC地址（0=随机） |
| `--badsum` | `nmap --badsum 192.168.1.1` | 发送错误校验和包（测试防火墙/IDS） |
| `--ttl` | `nmap --ttl 10 192.168.1.1` | 设置IP TTL值 |
| `--source-port` | `nmap --source-port 53 192.168.1.1` | 同 `-g`，指定源端口 |

**综合规避示例：**
```bash
nmap -f -T0 -n -Pn --data-length 200 -D 192.168.1.101,192.168.1.102,192.168.1.103,ME 192.168.1.1
```

---

## 10. 输出格式（Output）

| 参数 | 命令示例 | 说明 |
|------|---------|------|
| `-oN` | `nmap -oN result.nmap 192.168.1.1` | 正常文本输出 |
| `-oX` | `nmap -oX result.xml 192.168.1.1` | XML格式输出 |
| `-oG` | `nmap -oG result.gnmap 192.168.1.1` | Grepable格式输出 |
| `-oS` | `nmap -oS result.txt 192.168.1.1` | Script Kiddie格式（趣味输出） |
| `-oA` | `nmap -oA result 192.168.1.1` | 同时输出三种格式（.nmap, .xml, .gnmap） |
| `-v` | `nmap -v 192.168.1.1` | 详细输出 |
| `-vv` | `nmap -vv 192.168.1.1` | 更详细输出 |
| `-d` | `nmap -d 192.168.1.1` | 调试模式 |
| `--open` | `nmap --open 192.168.1.1` | 仅显示开放端口 |
| `--reason` | `nmap --reason 192.168.1.1` | 显示端口状态判定原因 |
| `--stats-every` | `nmap --stats-every 10s 192.168.1.1` | 定期显示扫描统计 |
| `--packet-trace` | `nmap --packet-trace 192.168.1.1` | 显示所有收发的包详情 |
| `--resume` | `nmap --resume result.nmap` | 恢复被中断的扫描 |

**输出处理技巧：**
```bash
# 提取开放端口列表
grep "open " result.nmap | sed -r 's/ +/ /g' | sort | uniq -c | sort -rn

# 从XML提取存活主机
nmap -oX out.xml 192.168.1.0/24 && grep "Nmap" out.xml | cut -d " " -f5 > live-hosts.txt

# XML转HTML
xsltproc result.xml -o result.html

# 对比两次扫描结果
ndiff scan1.xml scan2.xml
```

---

## 11. 端口状态说明

| 状态 | 含义 | 解读 |
|------|------|------|
| `open` | 开放 | 应用正在主动接受连接，是主要攻击面 |
| `closed` | 关闭 | 端口可访问但无服务监听，主机在线 |
| `filtered` | 过滤 | 防火墙/IDS拦截，无法确定端口状态 |
| `unfiltered` | 未过滤 | 端口可访问，但无法确定开放/关闭（ACK扫描） |
| `open\|filtered` | 开放或过滤 | 无法区分开放还是被过滤（UDP/NULL/FIN/Xmas扫描常见） |
| `closed\|filtered` | 关闭或过滤 | 无法区分关闭还是被过滤 |

---

## 12. 常用组合命令（Copy-Paste Ready）

### 12.1 快速侦察（Quick Recon）

```bash
# 主机发现（Ping扫描）
nmap -sn 192.168.1.0/24

# 快速Top 100端口扫描
nmap -F -T4 192.168.1.1

# 标准初始扫描（CTF/渗透测试首选）
nmap -sC -sV -T4 -oA initial 192.168.1.1

# 全端口扫描（后台运行）
nmap -p- -T4 -oA full_port 192.168.1.1
```

### 12.2 全面扫描（Comprehensive Scan）

```bash
# 综合扫描（OS+版本+脚本+traceroute）
nmap -A -T4 -p- -oA comprehensive 192.168.1.1

# 隐蔽SYN扫描+服务+OS
sudo nmap -sS -sV -O -T4 192.168.1.1

# TCP+UDP全扫描（最彻底但最慢）
sudo nmap -sS -sU -sV -O -sC -p- -T4 -oA fullscan 192.168.1.1
```

### 12.3 漏洞评估（Vulnerability Assessment）

```bash
# 通用漏洞扫描
nmap --script vuln -sV -oA vuln_scan 192.168.1.1

# Web服务漏洞
nmap -p 80,443,8080 --script http-vuln*,http-enum -sV 192.168.1.1

# SSL/TLS漏洞
nmap -p 443 --script ssl-heartbleed,ssl-poodle,ssl-enum-ciphers 192.168.1.1

# SMB漏洞
nmap -p 445 --script smb-vuln* 192.168.1.1

# 数据库漏洞
nmap -p 3306,1433,5432 --script mysql-vuln*,ms-sql-vuln* 192.168.1.1
```

### 12.4 服务枚举（Service Enumeration）

```bash
# Web服务枚举
nmap -p 80,443,8080 --script=http-enum,http-headers,http-methods,http-title -sV 192.168.1.1

# SMB枚举
nmap -p 445 --script smb-enum-shares,smb-enum-users,smb-os-discovery 192.168.1.1

# SSH枚举
nmap -p 22 --script ssh-auth-methods,ssh-hostk<response clipped><NOTE>Result is longer than **10000 characters**, will be **truncated**.</NOTE>