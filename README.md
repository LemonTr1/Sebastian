# Sebastian — 多 Agent 智能任务助手

> 本项目源自一次大学课程设计，因具有一定参考价值，故开源分享。

[English](README_EN.md) | 中文

[![Python](https://img.shields.io/badge/Python-%3E%3D3.10-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Version](https://img.shields.io/badge/Version-v0.2.0-orange)]()

Sebastian 是一个基于 LLM 的多 Agent 协作终端助手：主控 Agent 负责调度多个专业化子 Agent，在隔离沙箱中执行代码、操作文件、搜索网络，并具备跨会话的长期记忆能力。本项目源于一次大学课程设计，涵盖架构设计、安全防御与工程化实现等多个方面。

---

## 目录

- [设计哲学](#设计哲学)
- [架构概览](#架构概览)
- [核心特性](#核心特性)
  - [多 Agent 协作](#多-agent-协作)
  - [工具系统](#工具系统)
  - [记忆系统](#记忆系统)
  - [安全体系](#安全体系)
  - [人机协同审批](#人机协同审批)
  - [沙箱系统](#沙箱系统)
  - [Hook 系统](#hook-系统)
  - [上下文压缩](#上下文压缩)
  - [后台任务](#后台任务)
  - [会话管理](#会话管理)
  - [技能系统](#技能系统)
- [快速开始](#快速开始)
- [CLI 命令](#cli-命令)
- [项目结构](#项目结构)
- [技术栈](#技术栈)
- [许可证](#许可证)

---

## 设计哲学

Sebastian 的每一项设计决策都对应一条明确的设计原则。理解这些原则，即把握了整个系统的设计脉络。

### 1. 声明式设计 —— 能力即文件

**原则**：扩展系统能力不应以修改核心代码为前提。

**实现**：子 Agent 与技能均以纯 Markdown 文件（`YAML frontmatter` + 正文）定义，存放于约定目录，系统启动时自动扫描注册：

- 新增子 Agent → 在 `src/agents/subagents/`（或用户目录 `~/.sebastian/.agents/`）添加一份 `.md` 定义文件
- 新增技能 → 在 `~/.sebastian/skills/<name>/SKILL.md` 添加一份定义文件

无需修改任何代码，重启即生效。系统的可扩展性由文件系统约定（Convention over Configuration）保证，而非配置文件或插件 API。

### 2. 指挥与执行分离 —— 主控 Agent 不直接执行任务

**原则**：一个 Agent 若同时承担指挥与执行职责，其上下文规模将难以控制。

**实现**：Brain Agent（主控 Agent）仅负责意图解析与任务分派（triage）——理解用户意图、规划任务、调度子 Agent、汇总结果。四个子 Agent（CodeWriter / CodeReviewer / TestRunner / WebSearchAgent）各自维护独立的 LLM 上下文、专属工具集与系统提示词，任务完成后即被销毁。职责单一，提示词聚焦，上下文不受干扰。

### 3. 永不信任 LLM —— 模型输出须先通过安全检查

**原则**：LLM 的输出属于不可信的生成内容，其中任何命令、路径或 URL 均可能被诱导为攻击载荷。

**实现**：LLM 生成的每一条命令在执行前，均须经过四层纵深防御校验：

```
LLM 输出 → [命令安全] 拦截 rm -rf /、fork bomb 等 21 种危险模式
         → [路径安全] 强制绝对路径 + $HOME 限定 + 敏感目录黑名单
         → [网络安全] 拦截内网/回环/组播地址，防范 SSRF
用户输入 → [输入安全] 拦截提示注入/jailbreak
```

任何单一防护层被绕过均不会导致整体防线失效——纵深防御的意义在于消除单点故障。

### 4. 隔离优于信任 —— 以边界保障安全

**原则**：与其依赖对代码行为的假设，不如从机制上限制其能力。

**实现**：系统在三个层次上实施隔离：

| 隔离层次 | 手段 | 隔离对象 |
|----------|------|---------|
| 进程级 | 代码在 bubblewrap 命名空间沙箱中执行 | 宿主文件系统（只读挂载）、38 个敏感目录（tmpfs 隐藏）、系统能力（`cap-drop ALL`） |
| 进程级 | 审批确认窗口运行于独立 Python 子进程 | Tcl/Tk 线程安全问题——每个窗口拥有独立事件循环，任意线程调用均安全 |
| 上下文级 | 子 Agent 独立上下文，任务完成即销毁 | 子 Agent 之间的对话污染与嵌套调度 |

### 5. 优雅降级 —— 允许故障，但必须具备自恢复能力

**原则**：LLM 上下文窗口有限、API 服务会出现波动、模型可能返回空响应——故障属于常态而非例外。

**实现**：三层容错机制递进配合：

- **4 层上下文压缩管线**：大结果落盘 → 消息裁剪 → 微压缩 → LLM 摘要，确保上下文不超限
- **应急反应式压缩**：API 返回 `context_length_exceeded` 时立即压缩并重试（最多 3 次），对话不中断
- **指数退避重试**：API 故障自动重试（最多 5 次）；推理模型返回空内容时记录日志并降级处理，而非静默失效

### 6. 人机协同 —— 机器提出请求，人类做出决定

**原则**：自动化不等同于无人化。不可逆操作的最终决定权应始终保留给用户。

**实现**：危险操作（bash / write / edit / agent 调度）执行前，系统弹出独立置顶确认窗口，完整展示工具参数（语法高亮），支持键盘快捷键与超时自动拒绝。同时，记忆系统使 Sebastian 能够在跨会话间记录用户偏好与约束——记忆内容均来源于用户在对话中的明确表述。

---

## 架构概览

```
┌──────────────────────────────────────────────────────────────────┐
│                        CLI (Typer)                                │
│    UserPromptSubmit Hook → 输入安全检测 → Brain Agent             │
└─────────────────────────────┬────────────────────────────────────┘
                              │ 流式输出 + 记忆注入
         ┌────────────────────▼─────────────────────┐
         │              Brain Agent                  │
         │  · 意图解析与任务分派（Triage）            │
         │  · 任务规划（Todo Manager）                │
         │  · 记忆系统（选择 / 提取 / 整合）          │
         │  · 技能加载（Skill Registry）              │
         │  · 子Agent调度（支持后台异步）             │
         └──┬──────────┬──────────┬──────────┬──────┘
            │          │          │          │
    ┌───────▼──┐ ┌─────▼────┐ ┌──▼────┐ ┌──▼────────┐
    │CodeWriter│ │CodeReview│ │TestRnr│ │WebSearchAg│
    │ 6 tools  │ │ 4 tools  │ │5 tools│ │  2 tools  │
    └──────────┘ └──────────┘ └───────┘ └───────────┘

    所有工具调用经过 Hook 管道：
    PreToolUse → [日志记录] → [HITL 确认窗口]
    执行过程经过安全管道：
    命令防护 → 路径防护 → URL 防护 → bubblewrap 沙箱
```

**Brain Agent（主控 Agent）** 是唯一与用户交互的顶层 Agent，其系统提示词包含：路径安全底线、Bash 使用规范、常见任务调度策略表、任务规划指令、可用技能与子 Agent 清单、后台执行规则，以及动态注入的记忆索引。

---

## 核心特性

### 多 Agent 协作

Brain Agent 通过 `agent` 工具将子任务路由至专业化子 Agent；子 Agent 完成任务后被销毁，仅将最终结果返回给 Brain 进行自然语言汇总。子 Agent 定义采用纯 Markdown 格式（`YAML frontmatter` + 正文），支持用户自定义覆盖。

| 系统默认子 Agent        | 工具集 | 职责 |
|--------------------|--------|------|
| **CodeWriter**     | read, ls, glob, write, edit, grep | 阅读并理解现有代码，生成新代码 |
| **CodeReviewer**   | read, ls, glob, grep | 审查代码质量、风格与潜在问题 |
| **TestRunner**     | read, ls, bash, grep, glob | 执行测试并汇报结果（禁止修改测试代码） |
| **WebSearchAgent** | web_search, web_fetch | 网络搜索与网页内容提取 |

### 工具系统

所有工具注册于中央 `ToolsRegistry`，每项工具包含四个属性：名称、实现函数、JSON Schema、HITL 标记。工具按 Agent 分配——Brain Agent 可使用全部 12 项；子 Agent 的工具集在运行时动态注册（子 Agent 不允许嵌套调度其他子 Agent）。

| 工具 | HITL | 说明 |
|------|:----:|------|
| `bash` | ✓ | 在 bubblewrap 沙箱中执行 Shell 命令（支持后台异步） |
| `read` | | 读取文件（全文或偏移量+行数分片） |
| `write` | ✓ | 覆盖写入文件（阻止 PDF/DOCX） |
| `edit` | ✓ | 精确字符串查找替换（支持 replaceAll） |
| `ls` | | 列出目录内容 |
| `glob` | | 通配符匹配文件 |
| `grep` | | 正则内容搜索 |
| `web_search` | | DuckDuckGo 网页搜索（超时保护） |
| `web_fetch` | | 网页正文提取（SSRF 防护前置） |
| `todo` | | 任务规划与进度可视化 |
| `load_skill` | | 加载技能文档 |
| `agent` | ✓ | 调度子 Agent（支持后台异步） |

### 记忆系统

Sebastian 具备跨会话长期记忆能力，记忆数据存放于 `~/.sebastian/.memory/`，由三条 LLM 流水线驱动：

| 流程 | 触发时机 | 作用 |
|------|---------|------|
| **选择**（select） | 每轮对话开始 | 基于当前提问检索相关记忆，注入本轮上下文 |
| **提取**（extract） | 每轮对话结束 | 从对话中提取用户偏好、约束与项目事实，写入记忆文件 |
| **整合**（consolidate） | 记忆文件 ≥ 10 个 | 合并重复项、清理过期项、控制总量 |

记忆索引动态拼接至系统提示词（每次进入 AgentLoop 时刷新），记忆内容通过 `<relevant_memories>` 标签注入用户消息。记忆相关 API 调用自动关闭推理模型思考（`thinking: disabled`），并在后端不支持时回退，避免推理过程占用输出预算。

### 安全体系

四层纵深防御 + 一层人机确认：

| 层级 | 模块 | 职责 |
|------|------|------|
| 输入层 | `input_guard.py` | 提示注入/jailbreak 检测（中英文模式） |
| 命令层 | `command_guard.py` | 拦截 `rm -rf /`、fork bomb、`dd` 裸设备写入等 21 种危险模式 |
| 路径层 | `path_safety.py` | 绝对路径 + `$HOME` 限定 + 敏感目录/文件/扩展名黑名单 + 符号链接解析 |
| 网络层 | `url_safety.py` | SSRF 防护（拦截私有 IP 段、回环、链路本地、组播、IPv6 ULA） |
| 确认层 | HITL 确认窗口 | 破坏性操作须经用户确认方可执行 |

### 人机协同审批

HITL 采用子进程窗口方案（`approval_client.py` + `approval_dialog.py`）：

- 每次审批启动独立 Python 进程运行 tkinter 窗口，线程安全，任意 Agent 线程调用均无风险
- 参数卡片完整展示工具参数，附带语法高亮（字符串/数字/布尔分色）
- 支持键盘快捷键（Y/Enter 允许，N/Esc 拒绝）、倒计时超时自动拒绝
- 内置 dark / light / blue 三种主题

### 沙箱系统

代码执行基于 **bubblewrap** 实现 Linux 命名空间隔离：

- 命名空间：PID、IPC、UTS、cgroup 隔离；`--cap-drop ALL` 丢弃全部能力
- 宿主文件系统只读挂载，`~` 可写；**38 个敏感目录**（`.ssh`、`.aws`、浏览器配置、凭据存储、Shell 历史等）以 tmpfs 覆盖隐藏
- **21 个配置文件**（`.bashrc`、`.gitconfig`、语言工具链等）只读挂载
- 执行超时 180 秒；沙箱生命周期与父进程绑定，父进程退出时沙箱随之终止

### Hook 系统

事件驱动的插件机制，在 Agent 生命周期的四个节点注入自定义逻辑：

| 事件 | 触发阶段 | 已注册钩子 |
|------|----------|-----------|
| **UserPromptSubmit** | 用户输入后 | 输入安全检测 |
| **PreToolUse** | 工具执行前 | 调用日志 + HITL 确认窗口 |
| **PostCompletion** | LLM 响应完成后 | Token 消耗累计 |
| **Stop** | 一轮对话结束后 | 本轮 Token 消耗汇总 |

### 上下文压缩

**每 5 轮 AgentLoop 自动触发**四层递进式压缩管线：

1. **大结果落盘**：超过 50KB 的工具结果持久化至磁盘，上下文仅保留预览
2. **消息裁剪**：消息超过 50 条时保留前 3 + 后 47 条
3. **微压缩**：旧工具结果替换为占位符
4. **LLM 摘要**：超过 500K 字符时调用 API 生成对话摘要（原始对话存档为 transcript）

上下文溢出时另触发**应急反应式压缩**（最多 3 次重试）；`/compact` 命令可手动触发。

### 后台任务

`bash` 与 `agent` 工具支持 `run_in_background=true` 异步执行：任务在守护线程中运行，完成后通过 `<task_notification>` 主动通知 Brain Agent。Brain 的系统提示词内置后台调度规则：可并行执行的任务不串行等待，可异步完成的任务不阻塞主流程。

### 会话管理

- 会话保存为 JSONL 文件：`~/.sebastian/session/{session_id}.jsonl`
- 退出时自动保存，`sebastian -s <SESSION_ID>` 恢复会话；自动保留最近 10 个会话
- 对话内支持 `/clear` 清空历史、`/compact` 手动压缩

### 技能系统

技能文档存放于 `~/.sebastian/skills/<name>/SKILL.md`（YAML frontmatter + Markdown 正文），Brain Agent 通过 `load_skill` 工具按需加载。技能完全可插拔，添加或删除文件无需修改代码。已部署的示例技能包括：nmap、theHarvester、tcpdump、tshark、traceroute、whois、SSL 证书检查、子域名枚举等。

---

## 快速开始

### 环境要求

- **操作系统**：Linux（bubblewrap 沙箱依赖 Linux 命名空间）
- **Python**：>= 3.10
- **bubblewrap**：`sudo apt install bubblewrap`
- **python3-tk**：`sudo apt install python3-tk`（HITL 确认窗口依赖）
- **网络**：可访问 DeepSeek API（或任何兼容 OpenAI API 格式的后端）

### 安装

```bash
# 1. 克隆仓库
git clone <your-repo-url> Sebastian
cd Sebastian

# 2. 安装（推荐，自动注册 sebastian 命令）
pip install -e .

# 或使用 requirements.txt
pip install -r requirements.txt

# 3. 安装系统依赖 (Ubuntu/Debian)
sudo apt install bubblewrap python3-tk
```

### 配置 API Key

```bash
# 交互式配置向导（API Key 输入时前缀明文显示、其余以 * 掩码）
sebastian setup
```

配置写入项目根目录 `.env`：

```bash
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_API_KEY=sk-your-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

支持任何兼容 OpenAI API 格式的服务（OpenAI、DeepSeek、Ollama、vLLM 等）。

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

## CLI 命令

### 启动命令

```bash
sebastian                       # 标准启动（新建会话）
sebastian -v / --version        # 显示版本
sebastian -s <SESSION_ID>       # 恢复指定会话
sebastian --session <SESSION_ID>
sebastian setup                 # API 配置向导（密钥掩码输入）
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
├── cli.py                          # CLI入口（交互循环、会话保存/恢复、setup密钥掩码输入）
├── pyproject.toml                  # 项目元数据与依赖（setuptools）
├── requirements.txt                # 依赖清单（版本下限与注释）
├── .env                            # API密钥配置（gitignore保护）
│
├── src/
│   ├── config.py                   # LLM客户端配置（OpenAI兼容）
│   ├── agent_runner.py             # Agent核心引擎（对话循环/流式输出/HITL锁定/后台任务/周期压缩）
│   │
│   ├── agents/
│   │   ├── brain_agent.py          # Brain Agent 中央调度器（分派/任务规划/技能/子Agent/记忆）
│   │   └── subagents/              # 子Agent定义（Markdown + YAML frontmatter）
│   │       ├── code-writer.md      # 代码编写Agent（6工具）
│   │       ├── code-reviewer.md    # 代码审查Agent（4工具）
│   │       ├── test-runner.md      # 测试执行Agent（5工具）
│   │       └── web-search-agent.md # 网络搜索Agent（2工具）
│   │
│   ├── tools/
│   │   ├── tools_registry.py       # 工具注册中心（单例，按Agent分配，HITL标记）
│   │   └── toolkits/               # 12项工具实现
│   │       ├── bash.py             # 沙箱命令执行（支持后台）
│   │       ├── read.py / write.py / edit.py / ls.py / glob.py / grep.py
│   │       ├── web_search.py / web_fetch.py
│   │       ├── todo_manager.py     # 任务规划/进度提醒
│   │       ├── skill_registry.py   # 技能文档加载
│   │       └── subagent.py         # 子Agent生成/调度/动态工具注册
│   │
│   ├── security/                   # 4层安全防御
│   │   ├── input_guard.py          # 提示注入检测
│   │   ├── command_guard.py        # 高危命令拦截（21种模式）
│   │   ├── path_safety.py          # 路径安全校验
│   │   └── url_safety.py           # SSRF防护
│   │
│   ├── sandbox/
│   │   ├── bubblewrap.py           # bwrap沙箱管理器
│   │   └── settings.json           # 沙箱配置（38隐藏目录/21只读路径）
│   │
│   ├── hooks/                      # Event-driven钩子系统
│   │   ├── hooks_registry.py       # 钩子注册中心（4事件）
│   │   ├── user_prompt_submit/     # 输入安全检测
│   │   ├── pre_tool_use/           # 日志记录 + HITL确认窗口
│   │   ├── post_completion/        # Token统计
│   │   └── stop/                   # Token汇总
│   │
│   ├── prompts/                    # 可复用提示词片段
│   │   ├── bash.md                 # Bash工具使用规范
│   │   └── security_of_path.md     # 路径安全底线规则
│   │
│   ├── utils/                      # 工具函数
│   │   ├── memory_system.py        # 记忆系统（选择/提取/整合，关闭思考调用）
│   │   ├── compaction_pipeline.py  # 4层上下文压缩管线
│   │   ├── approval_client.py      # HITL确认窗口客户端（子进程IPC，线程安全）
│   │   ├── approval_dialog.py      # HITL确认窗口进程（tkinter，语法高亮）
│   │   ├── exceptions.py           # 自定义异常
│   │   ├── tokens_caculator.py     # 累计令牌计数
│   │   ├── session_id_container.py # 会话ID容器
│   │   ├── user_info.py            # 当前OS用户名
│   │   ├── datetime_utils.py       # 格式化时间
│   │   └── load_prompt.py          # 提示词片段加载
│   │
│   └── logs/
│       ├── app_log.py              # 循环日志记录器
│       └── sebastian.log           # 日志文件
```

用户数据目录（`~/.sebastian/`）：

```
~/.sebastian/
├── skills/             # 技能文档（SKILL.md）
├── .agents/            # 用户自定义子Agent（优先于内置）
├── .memory/            # 记忆文件 + MEMORY.md 索引
├── session/            # 会话存档（JSONL，保留最近10个）
├── .transcripts/       # 上下文压缩时的对话存档
└── .task_outputs/      # 大工具结果落盘
```

---

## 技术栈

| 分类 | 技术 |
|------|------|
| **语言** | Python >= 3.10 |
| **CLI 框架** | Typer |
| **LLM SDK** | OpenAI（兼容 DeepSeek / OpenAI / Ollama / vLLM） |
| **沙箱隔离** | bubblewrap（Linux 命名空间） |
| **确认窗口** | tkinter（子进程隔离，需 python3-tk） |
| **网页搜索** | DuckDuckGo（ddgs） |
| **配置管理** | python-dotenv |
| **构建系统** | setuptools |

依赖控制原则：仅保留代码实际使用的 4 个 pip 依赖（typer、openai、python-dotenv、ddgs），安装体积约 50MB。

---

## 许可证

MIT License

## 版本

**v0.2.0** — 大学课程设计作品，持续迭代中。
