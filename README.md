# Sebastian — 多Agent智能任务助手

> 基于 LLM 的多 Agent 协作终端助手，支持文件操作、代码沙箱执行、网页搜索与内容提取、向量知识库管理，配备四层纵深防御安全体系与 event-driven 钩子系统。

[![Python](https://img.shields.io/badge/Python-%3E%3D3.10-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## 目录

- [架构概览](#架构概览)
- [核心概念](#核心概念)
- [工具系统](#工具系统)
- [子Agent体系](#子agent体系)
- [安全体系](#安全体系)
- [沙箱系统](#沙箱系统)
- [Hook系统](#hook系统)
- [上下文压缩](#上下文压缩)
- [会话管理](#会话管理)
- [技能系统](#技能系统)
- [快速开始](#快速开始)
- [CLI命令](#cli命令)
- [项目结构](#项目结构)
- [技术栈](#技术栈)
- [设计要点](#设计要点)
- [许可证](#许可证)

---

## 架构概览

```
┌──────────────────────────────────────────────────────────────────┐
│                       CLI (Typer)                                 │
│               UserPromptSubmit Hook → 输入安全检测                 │
└─────────────────────────────┬────────────────────────────────────┘
                              │
         ┌────────────────────▼─────────────────────┐
         │              Brain Agent                  │
         │  · 意图路由（Triage）                      │
         │  · 任务规划（Todo Manager）                │
         │  · 技能加载（Skill Registry）              │
         │  · 子Agent调度（SubAgent Manager）         │
         └──┬──────────┬──────────┬──────────┬──────┘
            │          │          │          │
    ┌───────▼──┐ ┌─────▼────┐ ┌──▼────┐ ┌──▼────────┐
    │CodeWriter│ │CodeReview│ │TestRnr│ │WebSearchAg│
    │ 6 tools  │ │ 4 tools  │ │5 tools│ │  2 tools  │
    └──────────┘ └──────────┘ └───────┘ └───────────┘
```

**Brain Agent（中央调度器）** 负责分析用户意图并协调各个专业化子 Agent 完成复杂任务。Brain 自身不执行具体操作，而是通过工具调用（tool calls）将子任务路由给对应子 Agent。每个子 Agent 拥有独立的 LLM 对话上下文、专属工具集和定制化系统提示词。

---

## 核心概念

### Brain Agent — 主控大脑

Brain Agent 是唯一与用户交互的顶层 Agent，其系统提示词包含：

- 当前用户名与系统时间
- 文件路径安全底线规则（绝对路径、仅允许 `$HOME` 范围）
- Bash 工具使用规范（何时使用 Bash、何时使用结构化专用工具）
- 常见任务调度策略表（6 种情景 → 对应工具调用模式）
- 多步任务规划指令（必须用 todo 工具驱动，逐项完成逐项更新）
- 可用技能与子 Agent 列表

Brain Agent 支持**流式输出**，所有 LLM 响应 token 实时打印到终端。对于工具调用过程，以蓝色高亮显示工具名称和参数。

### 子 Agent — 专业化执行者

每个子 Agent 由纯 Markdown 文件定义（YAML 前置元数据 + 正文），包含 Agent 名称、描述和专属工具集。子 Agent 的 LLM 上下文与 Brain 完全隔离，任务完成后子 Agent 销毁，仅将最终结果返回给 Brain 做自然语言汇总。

### Agent 运行引擎（AgentRunner）

核心执行引擎 `src/agent_runner.py`（约 460 行）实现以下能力：

- LLM 对话循环（流式/非流式双模式）
- 工具调用解析与执行
- HITL 人机确认锁定机制（确认期间阻塞所有工具执行）
- 后台异步任务支持（`run_in_background` 参数，后台子Agent通过守护线程异步运行并主动通知主线程）
- 指数退避重试（LLM API 故障时最多 5 次）
- 上下文溢出时的应急反应式压缩（最多 3 次重试）
- 最大对话轮数硬限制（50 轮，防止无限循环）

---

## 工具系统

### 工具注册中心

所有工具注册在单例 `ToolsRegistry` 中，每项工具包含四个属性：

| 属性 | 说明 |
|------|------|
| `tool_name` | 工具名（LLM可见的函数名） |
| `tool_func` | 工具实现函数 |
| `schema` | OpenAI function-calling JSON Schema |
| `hitl` | 是否需要用户二次确认 |
| `for_agent` | 该工具归属的 Agent 名称 |

工具按 Agent 分配——Brain Agent 可使用 12 项工具（全部工具），各子 Agent 仅拥有其定义中声明的子集。

### 工具清单

#### Brain Agent 独占工具（12 项）

| 工具 | HITL | 说明 |
|------|:----:|------|
| `bash` | ✓ | 在 bubblewrap 沙箱中执行 Shell 命令 |
| `read` | | 读取文件内容（支持全文/偏移量+行数分片） |
| `write` | ✓ | 覆盖写入文件（阻止 PDF/DOCX 二进制覆盖） |
| `edit` | ✓ | 精确字符串查找替换（支持 `replaceAll`） |
| `ls` | | 列出目录内容 |
| `glob` | | 通配符匹配文件（最多返回 60 个结果） |
| `grep` | | 正则表达式内容搜索（子进程 grep，递归，最多 200 条） |
| `web_search` | | DuckDuckGo 网页搜索（ThreadPoolExecutor 超时保护） |
| `web_fetch` | | 网页正文提取（SSRF 防护前置检查） |
| `todo` | | 任务规划与进度可视化（pending/in_progress/completed） |
| `load_skill` | | 加载技能文档到当前对话 |
| `agent` | ✓ | 调度子 Agent 执行任务 |

#### 各子Agent工具分配

| 子Agent | 工具集 |
|---------|--------|
| **CodeWriter** | read, ls, glob, write, edit, grep |
| **CodeReviewer** | read, ls, glob, grep |
| **TestRunner** | read, ls, bash, grep, glob |
| **WebSearchAgent** | web_search, web_fetch |

---

## 子Agent体系

子 Agent 采用 **YAML frontmatter + Markdown body** 格式定义，存放于 `src/agents/subagents/*.md`。用户也可将自定义子 Agent 的 `.md` 文件放置到 `~/.sebastian/.agents/` 目录下实现扩展。

### 内置子Agent

**CodeWriter — 代码编写器**

- 工具集：read, ls, glob, write, edit, grep
- 职责：读取和理解现有代码结构，创建新代码文件或编辑已有代码
- 典型用途：根据需求生成代码片段、函数或模块

**CodeReviewer — 代码审查器**

- 工具集：read, ls, glob, grep
- 职责：分析代码质量、代码风格和潜在问题
- 典型用途：Review 代码变更、检查代码规范性

**TestRunner — 测试执行器**

- 工具集：read, ls, bash, grep, glob
- 职责：执行测试并报告结果；**严格禁止使用 Bash 编辑测试文件或修改测试代码**
- 典型用途：运行测试套件、汇总测试结果与错误日志

**WebSearchAgent — 网络搜索智能体**

- 工具集：web_search, web_fetch
- 职责：执行 Web 搜索并提取页面内容以获取实时信息
- 典型用途：搜索最新资讯、提取网页内容进行分析

---

## 安全体系

系统采用 **四层纵深防御 + 一层人机确认** 的安全架构，在用户输入 → LLM 生成 → 工具执行的每个阶段设置检查点：

```
用户输入 ──► [第一层] Input Guard ──► LLM 生成 ──► [第二层] Command Guard
                                                         │
                                               ┌─────────▼──────────┐
                                               │ [第三层] Path Safety │
                                               │ [第四层] URL Safety  │
                                               └─────────┬──────────┘
                                                         │
                                                    工具执行 ◄── [确认层] HITL
```

### 第一层：输入安全检测

**`input_guard.py`** — 提示注入检测

使用正则表达式检测用户输入中的越狱/提示注入攻击（涵盖中英文 7 种模式）：`ignore previous instructions`、`忽略之前的指令`、`System override`、`role play` 等。匹配后直接拒绝本次请求并记录日志。

### 第二层：命令安全检测

**`command_guard.py`** — 高危命令拦截

在执行任何 bash 命令之前，扫描命令字符串中的 21 种危险模式：

- `rm -rf /` — 递归删除根目录
- `mkfs.*` — 格式化文件系统
- fork bomb：`:(){ :|:& };:`
- `dd if=` — 裸设备写入
- `> /dev/sd[a-z]` — 覆盖磁盘设备
- `chmod 777 /` — 危险权限更改
- `wget ... -O /` — 下载到根目录
- `> /etc/` — 覆盖系统配置文件
- `eval` / `exec()` / `__import__('os')` / `subprocess.call` / `os.system` — 动态代码执行
- `fork bomb` 关键词、`shutdown -` / `reboot -` / `init 0/6` — 系统操作
- `iptables -F` — 清空防火墙规则

命中任意模式后抛出 `SecurityException`，终止执行。

### 第三层：路径安全校验

**`path_safety.py`** — 路径边界管控

所有文件操作类工具（read、write、edit、ls、glob、grep）在操作前强制执行：

- 路径必须为**绝对路径**
- 操作范围限定在 `$HOME` 目录内
- 解析符号链接（防止 `ln -s /etc/passwd ~/safe_link` 类逃逸攻击）
- **敏感目录黑名单**（拒绝访问）：`/etc`、`/proc`、`/sys`、`/dev`、`/boot`、`/root`、`/var/log`
- **敏感文件扩展名黑名单**（拒绝操作）：`.pem`、`.key`、`.pub`、`.cert`、`.crt`、`.pfx`、`.keystore`、`.jks`、`.env`、`.htpasswd`、`.credentials`
- **敏感文件名黑名单**（拒绝操作）：`.ssh/`、`.bashrc`、`.bash_history`、`id_rsa`、`id_ed25519`、`authorized_keys`、`known_hosts` 及其前缀/包含匹配

### 第四层：网络安全防护

**`url_safety.py`** — SSRF 防护

在 web_search 和 web_fetch 工具发起网络请求前，验证目标 URL：

- 拦截**私有 IP 段**：`10.0.0.0/8`、`172.16.0.0/12`、`192.168.0.0/16`
- 拦截**回环地址**：`127.0.0.0/8`、`::1`
- 拦截**链路本地地址**：`169.254.0.0/16`
- 拦截**组播地址**：`224.0.0.0/4`
- 拦截**文档/保留地址**：`240.0.0.0/4`
- 拦截 **IPv6** 链路本地 (`fe80::/10`) 和唯一本地 (`fc00::/7`)

### 确认层：人机协同（HITL）

对于标记为 HITL 的不可逆/破坏性操作，系统在 PreToolUse 阶段拦截工具调用并弹出终端确认提示：

```
⚠️  即将执行危险操作: [tool_name]
参数: {"key": "value", ...}
是否继续？[y/N]:
```

标记 HITL 的工具：`bash`、`write`、`edit`、`agent`。

---

## 沙箱系统

### Bubblewrap 隔离

代码执行基于 **bubblewrap (bwrap)** 实现 Linux 命名空间隔离：

| 隔离维度 | 配置 |
|----------|------|
| **命名空间** | PID、IPC、UTS、cgroup（全新命名空间） |
| **Capabilities** | 全部丢弃 (`--cap-drop ALL`) |
| **主机文件系统** | 默认只读挂载（不允许修改宿主机文件） |
| **Home 目录** | 可读写挂载（`~` 目录映射到沙箱内可写） |
| **敏感目录** | 38 个目录由 tmpfs 覆盖（完全隔离隐藏） |
| **敏感配置文件** | 21 个路径以只读方式挂载（可见但不可改） |
| **网络** | 可配置，当前默认：**允许** |
| **超时** | 180 秒（防止长时间占用或死循环） |
| **生命周期** | 随父进程退出自动终止 |

### 敏感目录隔离

沙箱将以下敏感路径以 **tmpfs（空文件系统）覆盖**，沙箱内代码完全无法感知这些目录的存在：

- 凭证类：`~/.ssh`、`~/.gnupg`、`~/.aws`、`~/.azure`、`~/.docker`
- 浏览器数据：`~/.mozilla`、`~/.config/google-chrome`、`~/.config/chromium`
- 通信应用：`~/.config/Signal`、`~/.config/telegram-desktop`、`~/.config/Slack`、`~/.thunderbird`
- 加密货币：`~/.bitcoin`、`~/.ethereum`
- 凭据存储：`~/.password-store`、`~/.local/share/keyrings`
- 历史记录：`~/.bash_history`、`~/.zsh_history`、`~/.python_history`

### 仅可读挂载

以下配置文件**可读但不可修改**，防止沙箱代码污染宿主环境：

- Shell 配置：`~/.bashrc`、`~/.zshrc`、`~/.profile`
- 编辑器配置：`~/.vimrc`、`~/.config/nvim`、`~/.emacs`
- 工具链：`~/.nvm`、`~/.rbenv`、`~/.pyenv`、`~/.rustup`、`~/.cargo`、`~/.gradle`、`~/.m2`

### 支持的语言运行时

沙箱内预配置了以下语言工具链（读取宿主只读挂载的工具链）：

- **Python** — 通过宿主 pyenv + pip
- **Bash** — 原生执行
- **C / C++** — 通过宿主的 gcc/g++
- **Java** — 通过宿主 JDK
- **Node.js** — 通过宿主 nvm
- **Go** — 通过宿主 Go toolchain
- **Rust** — 通过宿主 rustup + cargo

---

## Hook系统

基于事件驱动的钩子系统，在 Agent 生命周期的四个关键节点注入自定义逻辑：

| 事件 | 触发阶段 | 已注册钩子 |
|------|----------|-----------|
| **UserPromptSubmit** | 用户输入提交后，进入 AgentLoop 前 | 输入安全检测（检测 prompt injection） |
| **PreToolUse** | 工具调用执行前 | ① 工具调用日志记录 ② HITL 确认弹出（校验工具存在性、JSON 参数合法性、用户确认） |
| **PostCompletion** | LLM 一轮响应完成后 | 令牌消耗累计统计 |
| **Stop** | 一轮对话完全结束后 | 本轮令牌消耗汇总显示 |

所有钩子通过 `HooksRegistry` 单例管理。若钩子返回值非 `None`（表示拦截/错误），主流程将中断并返回钩子返回值。用户可根据需要向 `src/hooks/` 目录中添加自定义钩子模块。

---

## 上下文压缩

由于 LLM 存在上下文长度限制，系统实现了**四层递进式上下文压缩管线**（`CompactionPipeline`），在每次 Agent 循环结束后自动执行：

### 第一层：大结果落盘

工具执行结果 > 50KB 时，完整结果持久化到 `~/.sebastian/.task_outputs/tool-results/` 文件中，上下文内仅保留前 2000 字符预览 + 文件路径引用。

### 第二层：消息裁剪

当对话消息数 > 50 条时，保留**前 3 条**（初始上下文）+ **后 47 条**（最近交互），中间消息替换为省略占位符。裁剪边界对齐到消息角色边界（不在 assistant/tool 消息中间截断）。

### 第三层：微压缩

除最近 3 条消息外，将 > 150 字符的旧工具结果替换为简短占位符：`<SYSTEM_REMINDER>Earlier tool result compacted. Re-run if needed.</SYSTEM_REMINDER>`。

### 第四层：LLM API 摘要

当前三层压缩后字符串长度仍 > 500K 字符时，调用 LLM API 对整个对话进行摘要压缩。流程：
1. 将完整对话写入 `.transcript` 存档文件
2. 调用 LLM 生成对话摘要（保留：当前目标、关键发现/决策、已操作文件、剩余工作、用户约束条件）
3. 用摘要替换全部历史对话

### 应急反应式压缩

当 LLM API 返回上下文溢出错误时，触发反应式模式：先将上下文持久化为 transcript，再调用 LLM 生成摘要，合并最近 5 条消息，以最小上下文继续对话。最多重试 3 次。

### 手动压缩

用户在对话中输入 `/compact` 可手动触发第四层 LLM API 摘要压缩。

---

## 会话管理

### 会话保存与恢复

每次对话自动保存为 JSONL 格式的会话文件：

- **存储位置**：`~/.sebastian/session/{session_id}.jsonl`
- **Session ID 格式**：`YYYYMMDD-HHMM-xxxx`（时间戳 + 随机短哈希）
- **保存内容**：所有非 system 角色的消息（user / assistant / tool / function）
- **保存时机**：用户输入 `quit`、`/quit`、`/exit` 正常退出时
- **自动清理**：退出时保留最近 10 个会话文件，自动删除更早的会话

```
# 正常启动（创建新会话）
sebastian

# 恢复已有会话
sebastian -s 20260812-1530-a7f3
sebastian --session 20260812-1530-a7f3
```

### 对话转录存档

上下文压缩管线的第四层会生成 `.transcript` 存档文件，存放于 `~/.sebastian/.transcripts/transcript_{session_id}.txt`，便于后续追溯完整对话历史。

---

## 技能系统

### 技能注册

技能文档存放于 `~/.sebastian/skills/{skill_name}/SKILL.md`，采用与子 Agent 相同的 YAML frontmatter + Markdown body 格式。Brain Agent 在每次对话中可以通过 `load_skill` 工具动态加载技能。

### 工作流程

1. 用户请求某领域专项任务
2. Brain Agent 检测所需技能
3. 调用 `load_skill("<skill_name>")` 将技能文档追加到系统提示词
4. Brain Agent 根据技能指导执行任务

技能为可插拔设计——添加或删除 `SKILL.md` 文件无需修改任何代码即可生效。

---

## 快速开始

### 环境要求

- **操作系统**：Linux（bubblewrap 沙箱依赖 Linux 命名空间）
- **Python**：>= 3.10
- **bubblewrap**：`sudo apt install bubblewrap`
- **Playwright 浏览器**（可选，浏览器自动化时需）：`playwright install chromium`
- **网络**：需访问 DeepSeek API（或兼容 OpenAI API 的其他后端）

### 安装

```bash
# 1. 克隆仓库
git clone <your-repo-url> Sebastian
cd Sebastian

# 2. 安装项目及依赖
pip install -e .

# 3. 安装 bubblewrap 沙箱 (Ubuntu/Debian)
sudo apt install bubblewrap
```

### 配置 API Key

```bash
# 交互式配置向导
sebastian setup

# 按提示输入：
#   MODEL: deepseek-v4-flash
#   API_KEY: sk-your-api-key
#   BASE_URL: https://api.deepseek.com
```

配置将写入项目根目录的 `.env` 文件。支持任何兼容 OpenAI API 格式的后端服务（OpenAI、DeepSeek、Ollama、vLLM 等），只需调整 `.env` 中的对应参数即可。

### 启动

```bash
sebastian
```

```
Welcome lem0ntr1！I'm Sebastian. [输入 'quit' 退出]

[lem0ntr1]：帮我写一个计算斐波那契数列的 Python 脚本并运行它
[Sebastian]: 正在调度 CodeWriter 创建脚本...
  [CodeWriter]: 已创建 fib.py
[Sebastian]: 正在调度 TestRunner 运行脚本...
  [TestRunner]: fib(10) = 55，测试通过✓

[lem0ntr1]：quit
会话已保存，使用：sebastian -s 20260812-1530-a7f3 即可恢复会话
Bye
```

---

## CLI命令

### 启动命令

```bash
sebastian                       # 标准启动（新建会话）
sebastian -v                    # 显示版本信息
sebastian --version             # 显示版本信息
sebastian -s <SESSION_ID>       # 恢复指定会话
sebastian --session <SESSION_ID>  # 恢复指定会话
sebastian setup                 # API 配置向导
```

### 对话内命令

| 命令 | 说明 |
|------|------|
| `quit` / `/quit` / `/exit` | 保存会话并退出 |
| `/clear` | 清空当前对话历史 |
| `/compact` | 手动触发上下文 LLM 摘要压缩 |
| `Ctrl+C` / `Ctrl+D` | 退出（不保存会话） |

---

## 项目结构

```
Sebastian/
├── cli.py                          # CLI入口（Typer交互式聊天循环、会话保存/恢复）
├── pyproject.toml                  # 项目配置与依赖（setuptools构建系统）
├── .env                            # API密钥配置（gitignore保护）
│
├── src/
│   ├── config.py                   # LLM客户端配置（DeepSeek/OpenAI兼容）
│   ├── agent_runner.py             # Agent核心引擎（对话循环/流式输出/HITL锁定/后台任务/压缩）
│   │
│   ├── agents/
│   │   ├── brain_agent.py          # Brain Agent 中央调度器（路由/任务规划/技能/子Agent调度）
│   │   └── subagents/              # 子Agent定义（Markdown + YAML frontmatter）
│   │       ├── code-writer.md      # 代码编写Agent（6工具）
│   │       ├── code-reviewer.md    # 代码审查Agent（4工具）
│   │       ├── test-runner.md      # 测试执行Agent（5工具）
│   │       └── web-search-agent.md # 网络搜索Agent（2工具）
│   │
│   ├── tools/
│   │   ├── tools_registry.py       # 工具注册中心（单例，按Agent分配）
│   │   └── toolkits/               # 工具实现模块
│   │       ├── bash.py             # 沙箱命令执行
│   │       ├── read.py             # 文件读取（全文/偏移量）
│   │       ├── write.py            # 文件覆写
│   │       ├── edit.py             # 文件编辑（查找替换）
│   │       ├── ls.py               # 目录列表
│   │       ├── glob.py             # 通配符文件匹配
│   │       ├── grep.py             # 正则内容搜索
│   │       ├── web_search.py       # DuckDuckGo网页搜索
│   │       ├── web_fetch.py        # 网页正文提取
│   │       ├── todo_manager.py     # 任务规划/进度管理
│   │       ├── skill_registry.py   # 技能文档注册与加载
│   │       └── subagent.py         # 子Agent生成与管理
│   │
│   ├── security/                   # 4层安全防御
│   │   ├── input_guard.py          # 提示注入检测（7种模式）
│   │   ├── command_guard.py        # 高危命令拦截（21种模式）
│   │   ├── path_safety.py          # 路径安全校验（$HOME限定/敏感目录/符号链接）
│   │   └── url_safety.py           # SSRF防护（私有IP/内网地址拦截）
│   │
│   ├── sandbox/
│   │   ├── bubblewrap.py           # bwrap沙箱管理器
│   │   └── settings.json           # 沙箱配置（38隔离目录/21只读路径/超时/网络）
│   │
│   ├── hooks/                      # Event-driven钩子系统
│   │   ├── hooks_registry.py       # 钩子注册中心
│   │   ├── user_prompt_submit/     # 用户输入阶段钩子
│   │   │   └── check_input_security.py
│   │   ├── pre_tool_use/           # 工具执行前钩子
│   │   │   ├── 01_log_hook.py      # 工具调用日志
│   │   │   └── 02_hitl_hook.py     # 人机确认弹窗
│   │   ├── post_completion/        # 响应完成后钩子
│   │   │   └── calculate_tokens.py # 令牌统计
│   │   └── stop/                   # 对话轮次结束钩子
│   │       └── summarize_tokens.py # 令牌消耗汇总
│   │
│   ├── prompts/                    # 可复用提示词片段
│   │   ├── bash.md                 # Bash工具使用规范
│   │   └── security_of_path.md     # 路径安全底线规则
│   │
│   ├── utils/                      # 工具函数
│   │   ├── exceptions.py           # 自定义异常（Security/Compact/SubAgent）
│   │   ├── compaction_pipeline.py  # 4层上下文压缩管线
│   │   ├── tokens_caculator.py     # 累计令牌计数
│   │   ├── session_id_container.py # 会话ID容器
│   │   ├── user_info.py            # 获取当前OS用户名
│   │   ├── datetime_utils.py       # 格式化当前时间
│   │   └── load_prompt.py          # 加载提示词片段文件
│   │
│   └── logs/
│       ├── app_log.py              # 循环日志记录器
│       └── sebastian.log           # 日志文件
```

---

## 技术栈

| 分类 | 技术 |
|------|------|
| **语言** | Python >= 3.10 |
| **CLI 框架** | Typer |
| **LLM SDK** | OpenAI（兼容 DeepSeek / OpenAI / Ollama / vLLM） |
| **沙箱隔离** | bubblewrap（Linux 命名空间：PID/IPC/UTS/cgroup） |
| **向量数据库** | ChromaDB |
| **Embedding** | sentence-transformers（all-MiniLM-L6-v2） |
| **网页搜索** | DuckDuckGo（ddgs） |
| **浏览器自动化** | Playwright（Chromium） |
| **文档处理** | python-docx / python-pptx / kreuzberg |
| **HTTP 客户端** | httpx |
| **压缩支持** | py7zr + shutil |
| **数据校验** | pydantic |
| **配置管理** | python-dotenv |
| **构建系统** | setuptools >= 59.6.0 |

---

## 设计要点

### 多 Agent 协作

Brain Agent 作为唯一用户界面，通过 `agent` 工具调度子 Agent 执行专业化任务。每个子 Agent 维持独立的 LLM 对话上下文和工具集，任务完成后即销毁，仅向 Brain 返回最终结果。任务分解由 Todo Manager 驱动，支持终端内进度可视化：

```
[✓] 分析需求
[>] 创建项目结构
[ ] 编写核心代码
[ ] 运行测试验证
```

子 Agent 定义采用纯 Markdown 格式，添加新子 Agent 只需在 `src/agents/subagents/` 或 `~/.sebastian/.agents/` 中创建新 `.md` 文件。

### 安全纵深防御

安全体系覆盖攻击全链路——从用户提权注入（Input Guard）到 LLM 恶意代码生成（Command Guard），再到文件路径逃逸（Path Safety）和 SSRF 内网扫描（URL Safety），最终由 HITL 人机确认兜底破坏性操作。各层独立运行、层层递进，某一层被绕过不会导致整个安全体系失效。

### 人机协同（HITL）

对于不可逆操作，系统在 PreToolUse 阶段拦截并弹出终端确认提示，要求用户输入 `y/n` 方可执行。标记 HITL 的工具：bash、write、edit、agent。HITL 确认期间整个 Agent 循环被锁定，阻止其他工具并发执行确保状态一致。

### 上下文管理

四层递进式压缩管线解决了 LLM 上下文窗口限制问题。前两层（大结果落盘、消息裁剪）无 LLM API 开销；第三层（微压缩）以最小代价缩减工具历史；第四层（LLM 摘要）作为终极手段，仅在绝对必要时触发。搭配应急反应式压缩，即使超长对话也能自愈恢复。

---

## 许可证

MIT License

---

## 版本

**v0.2.0** — 毕业设计作品，持续迭代中。
