---
name: theharvester-osint
description: >
  theHarvester 开源情报（OSINT）收集工具。用于在渗透测试或红队评估的侦察阶段，
  从多个公共数据源（搜索引擎、证书透明度日志、社交媒体、威胁情报平台等）收集
  目标域名的电子邮件地址、子域名、IP地址、员工姓名、开放端口/横幅和URL。
  触发条件：用户提及 theHarvester、OSINT收集、子域名枚举、邮箱收集、
  被动信息收集、 reconnaissance、信息侦察、开源情报等关键词。
keywords:
  - theHarvester
  - theharvester
  - OSINT
  - 开源情报
  - 信息收集
  - 侦察
  - reconnaissance
  - 子域名枚举
  - 邮箱收集
  - 被动收集
  - 渗透测试前期
  - subdomain enumeration
  - email harvesting
  - footprinting
---

# theHarvester 开源情报收集工具

## 概述

theHarvester 是由 Christian Martorella 开发的 Python 开源情报（OSINT）收集工具，
用于在渗透测试或红队评估的早期侦察阶段，确定目标域名在互联网上的外部威胁态势。
该工具通过调用多个公开数据源，被动收集以下信息：

- **电子邮件地址** — 用于钓鱼测试或社会工程学攻击
- **子域名** — 发现攻击面和被遗忘的资产
- **IP 地址** — 映射目标网络基础设施
- **员工姓名/用户名** — 用于账户枚举或社交工程
- **开放端口与横幅** — 通过 Shodan 等引擎获取服务信息
- **URL 链接** — 发现暴露的 Web 资产

> **法律与道德声明**：仅对授权目标或自有资产使用该工具。遵守当地法律法规（如 GDPR）。
> 仅收集公开数据，不得用于非法入侵或骚扰。

---

## 安装

### 前置要求

- Python 3.12 或更高版本
- `uv` 包管理器（推荐）或 `pip`

### 安装步骤

```bash
# 1. 安装 uv（如未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 克隆仓库
git clone https://github.com/laramies/theHarvester.git
cd theHarvester

# 3. 安装依赖并创建虚拟环境
uv sync

# 4. 运行
theHarvester -h
# 或
uv run theHarvester -h
```

### Kali Linux（预装）

```bash
sudo apt update
sudo apt install theharvester
theHarvester -h
```

### Docker 方式

```bash
docker pull laramies/theharvester
docker run --rm laramies/theharvester -h
```

---

## 核心命令参数

| 参数 | 长参数 | 说明 | 示例 |
|------|--------|------|------|
| `-d` | `--domain` | **目标域名**（必填） | `-d example.com` |
| `-b` | `--source` | **数据源**（见下方数据源列表） | `-b all` 或 `-b google,crtsh,shodan` |
| `-l` | `--limit` | 限制返回结果数量，默认 500 | `-l 100` |
| `-S` | `--start` | 从第 X 个结果开始，默认 0 | `-S 0` |
| `-f` | `--filename` | 输出文件名（支持 HTML/XML） | `-f results` |
| `-s` | `--shodan` | 对发现的主机使用 Shodan 查询端口/横幅 | `-s` |
| `-v` | `--virtual-host` | 通过 DNS 解析验证主机名并搜索虚拟主机 | `-v` |
| `-e` | `--dns-server` | 指定 DNS 服务器 | `-e 8.8.8.8` |
| `-c` | `--dns-brute` | 启用 DNS 字典暴力破解枚举子域名 | `-c` |
| `-t` | `--take-over` | 检查子域名接管漏洞 | `-t` |
| `--screenshot` | `--screenshot` | 对发现的子域名截图，需指定输出目录 | `--screenshot ./screenshots` |
| `-p` | `--proxies` | 使用代理（在 `proxies.yaml` 中配置） | `-p` |
| `-g` | `--google-dork` | 使用 Google Dorks 进行搜索 | `-g` |
| `-r` | `--dns-resolve` | 对发现的所有 IP 执行 DNS 反向查询 | `-r` |
| `-n` | `--dns-lookup` | 对发现的所有范围执行 DNS 反向查询 | `-n` |
| `-h` | `--help` | 显示帮助信息 | `-h` |

---

## 数据源（-b 参数）

### 免费数据源（无需 API Key）

| 数据源 | 说明 | 收集类型 |
|--------|------|----------|
| `google` | Google 搜索引擎 | 邮箱、子域名、URL |
| `bing` | Microsoft Bing 搜索引擎 | 邮箱、子域名 |
| `duckduckgo` | DuckDuckGo 搜索引擎 | 邮箱、子域名 |
| `yahoo` | Yahoo 搜索引擎 | 邮箱、子域名 |
| `baidu` | 百度搜索引擎 | 邮箱、子域名 |
| `crtsh` | Comodo 证书透明度日志搜索 | 子域名 |
| `certspotter` | Cert Spotter 证书监控 | 子域名 |
| `hackertarget` | HackerTarget 在线扫描器 | 子域名、IP |
| `rapiddns` | RapidDNS 查询工具 | 子域名、IP |
| `threatminer` | 威胁情报数据挖掘 | 子域名、邮箱 |
| `urlscan` | URL 和网站扫描沙箱 | URL、子域名 |
| `dnsdumpster` | DNS 域研究工具 | 子域名、DNS 记录 |
| `subdomaincenter` | 子域名查找工具 | 子域名 |
| `subdomainfinderc99` | C99 子域名查找器 | 子域名 |
| `thc` | THC 免费子域名枚举服务 | 子域名 |
| `otx` | AlienVault 开放威胁交换 | 子域名、IP |
| `vhost` | Bing 虚拟主机搜索 | 虚拟主机 |
| `sitedossier` | 站点信息查询 | 子域名 |
| `anubis` | Anubis-DB 子域名数据库 | 子域名 |
| `all` | 调用所有**免费/有效**数据源的子集 | 综合 |

### 需要 API Key 的数据源

> 使用前需在 `api-keys.yaml` 中配置对应 API Key。

| 数据源 | 说明 | 免费额度 | 付费参考 |
|--------|------|----------|----------|
| `shodan` | Shodan 网络空间搜索引擎 | 有限 | Freelancer $69/月 |
| `censys` | Censys 证书/主机搜索 | 有限 | 500 credits $100 |
| `virustotal` | VirusTotal 域名搜索 | 500 次/天 | 企业版需工作邮箱 |
| `hunter` | Hunter.io 邮箱搜索引擎 | 50 次/月 | 12k credits/年 $34 |
| `securityTrails` | 历史 DNS 数据仓库 | 50 次/月 | 20k 次/月 $500 |
| `intelx` | Intelligence X 搜索引擎 | 非常有限 | 商业版 $2900 |
| `github-code` | GitHub 代码搜索 | 需 GitHub PAT | — |
| `netlas` | Netlas 攻击面搜索 | 50 次/天 | 1k 次 $49 |
| `onyphe` | 网络防御搜索引擎 | 有限 | 10M 结果/月 $587 |
| `fofa` | FOFA 网络空间搜索引擎 | 有限 | 10k 查询/月 $25 |
| `zoomeye` | ZoomEye 网络空间搜索引擎 | 5 次/天 | 30 次/天 $190/年 |
| `bevigil` | BeVigil 移动应用 OSINT | 50 次/月 | 1k 次/月 $50 |
| `brave` | Brave 搜索 API | 有免费计划 | Pro 计划 |
| `bufferoverun` | TLS 证书 IPv4 查询 | 100 次/月 | 10k 次/月 $25 |
| `criminalip` | 网络威胁情报搜索引擎 | 100 次/月 | 700k 次/月 $59 |
| `dehashed` | 数据泄露搜索引擎 | 有限 | 500 credits $15 |
| `fullhunt` | 攻击面安全平台 | 50 次 | 200 次/月 $29 |
| `haveibeenpwned` | 数据泄露邮箱检查 | 有限 | 10 次/分 $4.50 |
| `hunterhow` | 安全研究员搜索引擎 | 10k 次/30天 | 50k 次/30天 $10 |
| `leakix` | 泄露数据搜索引擎 | 25 页 | Bounty Hunter $29 |
| `leaklookup` | 数据泄露搜索引擎 | 有限 | 20 credits $10 |
| `mojeek` | Mojeek 搜索引擎 | 5000 credits $6.50 | 按 CPM 计费 |
| `pentesttools` | 云端渗透测试工具包 | 有限 | 5 assets $95/月 |
| `projecdiscovery` | ProjectDiscovery Chaos | 需工作邮箱 | 企业版 |
| `rocketreach` | 邮箱/电话/社交链接查找 | 有限 | 100 次/月 $48 |
| `securityscorecard` | 供应商风险评估 | 需工作邮箱 | 企业版 |
| `sherlockeye` | 反向查找与 AI OSINT | 有限 | 中级 $46/月 |
| `tomba` | Tomba 邮箱搜索引擎 | 25 次/月 | 1k 次/月 $39 |
| `venacus` | Venacus 搜索引擎 | 1 次/天 | 10 次/天 $12 |
| `whoisxml` | WhoisXML 子域名搜索 | 有限 | 2k 次 $50 |
| `windvane` | Windvane 搜索引擎 | 100 次免费 | — |
| `builtwith` | 网站技术栈检测 | 50 次终身 | $2950/年 |
| `dymo` | Dymo 域名验证与欺诈检测 | 有免费计划 | 付费计划 |

---

## API Key 配置

编辑项目根目录下的 `api-keys.yaml` 文件，填入对应服务的 API Key：

```yaml
apikeys:
  bing:
    key: "YOUR_BING_API_KEY"
  github:
    key: "YOUR_GITHUB_PERSONAL_ACCESS_TOKEN"
  hunter:
    key: "YOUR_HUNTER_API_KEY"
  intelx:
    key: "YOUR_INTELX_API_KEY"
  securityTrails:
    key: "YOUR_SECURITYTRAILS_API_KEY"
  shodan:
    key: "YOUR_SHODAN_API_KEY"
  censys:
    id: "YOUR_CENSYS_ID"
    secret: "YOUR_CENSYS_SECRET"
  virustotal:
    key: "YOUR_VIRUSTOTAL_API_KEY"
  # ... 其他服务
```

> 获取 API Key 的文档：https://github.com/laramies/theHarvester/wiki/Installation#api-keys

---

## 常用工作流与示例

### 1. 基础域名信息收集（免费源）

```bash
# 使用多个免费搜索引擎收集邮箱和子域名
theHarvester -d example.com -b google,bing,duckduckgo,crtsh -l 200 -f example_basic

# 使用 all 自动调用所有免费/有效数据源
theHarvester -d example.com -b all -l 500 -f example_all
```

### 2. 深度子域名枚举（含 DNS 暴力破解）

```bash
# 结合被动收集 + DNS 字典暴力破解 + 虚拟主机验证
theHarvester -d example.com -b all -c -v -e 8.8.8.8 -f example_subdomains
```

### 3. 结合 Shodan 进行端口/横幅探测

```bash
# 先收集子域名和 IP，再通过 Shodan 查询开放端口和服务横幅
# 需要配置 shodan API key
theHarvester -d example.com -b all -s -f example_shodan
```

### 4. 子域名截图（可视化侦察）

```bash
# 对发现的所有子域名进行网页截图，保存到指定目录
theHarvester -d example.com -b all --screenshot ./screenshots -f example_screenshots
```

### 5. 邮箱定向收集（用于钓鱼测试）

```bash
# 使用 Hunter.io + Google + Bing 收集员工邮箱
# 需要配置 hunter API key
theHarvester -d example.com -b hunter,google,bing,linkedin -l 100 -f example_emails
```

### 6. 证书透明度日志专项收集

```bash
# 仅使用证书透明度日志源，发现通过证书注册的子域名
theHarvester -d example.com -b crtsh,certspotter,censys -l 500 -f example_certs
```

### 7. 批量扫描多个目标

```bash
# 使用 shell 循环批量扫描多个域名
for domain in $(cat targets.txt); do
  theHarvester -d $domain -b all -f "results_${domain}" -l 300
done
```

### 8. 通过代理进行匿名收集

```bash
# 配置 proxies.yaml 后使用代理
# proxies.yaml 示例：
# http:
#   - http://127.0.0.1:8080
# https:
#   - https://127.0.0.1:8080

theHarvester -d example.com -b all -p -f example_proxy
```

---

## 输出格式说明

- **终端输出**：默认在终端显示收集到的邮箱、子域名、IP、员工姓名等
- **HTML 报告**：使用 `-f filename` 生成可视化 HTML 报告，便于查看和分享
- **XML 导出**：同时生成 XML 格式，便于与其他工具集成或自动化处理
- **截图目录**：使用 `--screenshot` 时，子域名截图保存在指定目录

---

## 最佳实践

1. **从单一数据源开始**：初次使用某个目标时，先使用 `-b google` 等单一源了解输出格式，再使用 `all`
2. **限制结果数量**：使用 `-l` 参数避免数据过载，根据目标大小调整（50-500 为宜）
3. **保存输出**：始终使用 `-f` 参数保存结果，便于后续分析和团队协作
4. **交叉验证**：将 theHarvester 的结果与其他 OSINT 工具（如 Maltego、Amass、Subfinder）交叉验证
5. **定期更新**：通过 `git pull` 或包管理器保持工具更新，以获取最新数据源和功能
6. **尊重速率限制**：部分免费数据源有请求频率限制，避免过快请求导致 IP 被封
7. **配置 API Key**：对于常用的高级数据源（如 Shodan、VirusTotal），提前配置 API Key 可大幅提升收集效率

---

## 故障排查

| 问题 | 解决方案 |
|------|----------|
| `ModuleNotFoundError` | 确保在虚拟环境中运行：`uv sync` 或 `pip install -r requirements.txt` |
| API 源返回空结果 | 检查 `api-keys.yaml` 中对应 Key 是否正确；确认是否超出免费额度 |
| Google 搜索无结果 | Google 可能拦截了请求，尝试使用代理 `-p` 或更换数据源 |
| DNS 暴力破解无结果 | 检查字典文件路径；尝试指定其他 DNS 服务器 `-e 1.1.1.1` |
| 截图功能失败 | 确保已安装浏览器依赖（如 Chromium）；检查输出目录权限 |
| `all` 源跳过某些模块 | 正常现象，`all` 仅调用当前有效/免费的子集，不代表所有模块 |

---

## 相关工具对比

| 工具 | 主要用途 | 与 theHarvester 的关系 |
|------|----------|----------------------|
| **Amass** | 深度子域名枚举与网络映射 | 功能更强，但配置更复杂；可互补使用 |
| **Subfinder** | 高速子域名发现 | 专注于子域名，速度更快；可与 theHarvester 结果合并 |
| **Recon-ng** | 全功能侦察框架 | 模块化框架，功能更全面；学习曲线更陡 |
| **Maltego** | 数据可视化与关联分析 | 可视化能力强；可将 theHarvester 输出导入做关联分析 |
| **Shodan CLI** | 网络空间设备搜索 | theHarvester 通过 `-s` 参数调用 Shodan 做二次探测 |

---

## 参考资源

- **官方仓库**：https://github.com/laramies/theHarvester
- **安装文档**：https://github.com/laramies/theHarvester/wiki/Installation
- **API Key 配置**：https://github.com/laramies/theHarvester/wiki/Installation#api-keys
- **Docker 镜像**：https://github.com/laramies/theHarvester/pkgs/container/theharvester
- **作者 Twitter**：@laramies
- **问题反馈**：https://github.com/laramies/theHarvester/issues