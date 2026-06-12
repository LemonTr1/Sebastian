# Sebastian — 多Agent智能任务助手

> 基于 LLM 的多 Agent 协作终端助手，支持文件操作、代码沙箱执行、网页搜索、浏览器自动化与向量知识库管理。

[![Python](https://img.shields.io/badge/Python-%3E%3D3.10-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## 架构概览

```
┌────────────────────────────────────────────────────────┐
│                     CLI (Typer)                         │
│                 输入安全检测 → Brain Agent               │
└───────────────────────┬────────────────────────────────┘
                        │
          ┌─────────────▼─────────────┐
          │     Brain Agent (Triage)  │
          │   · 意图路由 Dispatcher    │
          │   · 任务规划 Todo Manager  │
          │   · 技能注册 Skill Registry│
          └──┬────────┬────────┬──────┘
             │        │        │
   ┌─────────▼──┐ ┌──▼────┐ ┌▼─────────┐ ┌──────────┐
   │ File Agent │ │ Code  │ │ Web Agent│ │ Memory   │
   │ 19 tools   │ │ Agent │ │ 15 tools │ │ Agent    │
   │            │ │sandbox│ │          │ │ 4 tools  │
   └────────────┘ └───────┘ └──────────┘ └──────────┘
```

Brain Agent 作为中央调度器，分析用户意图后将任务分发给四个专业化子 Agent，子 Agent 将执行结果返回给 Brain 做最终的自然语言汇总。

---

## 功能特性

### 文件操作 (File Agent)
- 目录操作：`ls`、`mkdir`、`cp`、`mv`、`rm`、`rename`、`touch`
- 文件读写：读/写/编辑文本文件、创建空文件
- 文档处理：DOCX 文档创建/读取/编辑、PDF 文本提取、PPTX 幻灯片提取
- 压缩解压：支持 zip / tar / tar.gz / 7z 格式

### 代码沙箱 (Code Agent)
- 基于 **bubblewrap (bwrap)** 的 Linux 命名空间隔离沙箱
- 支持语言：Python、Bash、C、C++、Java、Node.js、Go、Rust
- 包管理器缓存持久化（pip / npm / cargo / go mod）
- 宿主文件只读挂载，沙箱内 `/workspace` 可写，出沙箱无残留
- 执行前自动安全审核（拦截 `rm -rf /`、fork bomb、反弹 shell 等）

### 网络与浏览器 (Web Agent)
- DuckDuckGo 网络搜索 + 网页正文提取
- 文件下载（流式扫描、魔术字节校验、Content-Type 对比、双重扩展名检测、归档文件内扫描）
- Playwright 浏览器自动化（导航/点击/填表/截图/滚动/JS 执行/Cookie 管理）

### 知识库 (Memory Agent)
- 基于 **ChromaDB** 的向量存储
- 语义检索（embedding 引擎：`all-MiniLM-L6-v2` via sentence-transformers）
- 支持多集合管理

### 安全体系
| 层级 | 模块 | 职责 |
|------|------|------|
| 输入层 | `input_guard.py` | 提示注入检测（正则匹配 jailbreak / prompt override / 路径遍历） |
| 命令层 | `command_guard.py` | 高危命令拦截（`rm -rf /`、fork bomb、`shutdown` 等 21 种模式） |
| 路径层 | `path_safety.py` | 路径校验（仅允许 `$HOME` 子目录、拒绝敏感目录/文件/扩展名、防符号链接逃逸） |
| 网络层 | `url_safety.py` | SSRF 防护（拦截私有/内网 IP 段） |
| 确认层 | HITL | 破坏性操作（编辑/删除/重命名/移动/下载）须用户二次确认 |

---

## 快速开始

### 环境要求

- **Python** >= 3.10
- **Linux**（bubblewrap 沙箱依赖 Linux 命名空间）
- **bubblewrap** (`sudo apt install bubblewrap`)
- **Playwright 浏览器**（`playwright install chromium`）

### 安装

```bash
# 1. 克隆仓库
git clone <your-repo-url> Sebastian
cd Sebastian

# 2. 安装依赖
pip install -e .

# 3. 安装 Playwright 浏览器
playwright install chromium

# 4. 安装 bubblewrap 沙箱 (Ubuntu/Debian)
sudo apt install bubblewrap
```

### 配置 API Key

```bash
# 交互式配置
sebastian setup

# 或直接编辑 .env 文件
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_API_KEY=sk-your-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

默认后端为 **DeepSeek**，支持任何兼容 OpenAI API 格式的服务（如 OpenAI、Ollama、vLLM 等）。

### 启动

```bash
sebastian
```

```
Welcome lem0ntr1！I'm Sebastian. [输入 'quit' 退出]

[lem0ntr1]：帮我在桌面上创建一个名为"项目计划.docx"的空白docx文档
[Sebastian]: 已成功在 /home/lem0ntr1/桌面/项目计划.docx 创建空白文档...

[lem0ntr1]：帮我搜索一下最新的Python 3.13发布了哪些新特性，保存到桌面
[Sebastian]: 搜索结果为...已保存到 /home/lem0ntr1/桌面/Python3.13新特性.txt

[lem0ntr1]：quit
Bye
```

---

## 技术栈

| 分类 | 技术 |
|------|------|
| **CLI 框架** | Typer |
| **LLM SDK** | OpenAI (兼容 DeepSeek / OpenAI / Ollama) |
| **向量数据库** | ChromaDB |
| **Embedding** | sentence-transformers (all-MiniLM-L6-v2) |
| **浏览器自动化** | Playwright (Chromium) |
| **网页搜索** | DuckDuckGo (ddgs) |
| **HTTP 客户端** | httpx |
| **文档处理** | python-docx / python-pptx / kreuzberg |
| **压缩支持** | py7zr + shutil |
| **沙箱隔离** | bubblewrap (Linux namespaces) |
| **配置管理** | python-dotenv |
| **数据校验** | pydantic |

---

## 项目结构

```
Sebastian/
├── cli.py                      # CLI 入口（Typer，交互式聊天循环）
├── pyproject.toml              # 项目配置与依赖
├── .env                        # API 密钥（gitignore 保护）
│
├── src/
│   ├── agent_runner.py         # Agent 核心引擎（LLM 对话循环 + 流式输出 + HITL 确认）
│   ├── config.py               # LLM 客户端配置
│   │
│   ├── agents/                 # Agent 定义
│   │   ├── brain_agent.py      # 中央调度器（路由 + 任务规划 + 技能系统）
│   │   ├── file_agent.py       # 文件操作 Agent（19 工具）
│   │   ├── code_agent.py       # 代码沙箱 Agent
│   │   ├── web_agent.py        # 网络搜索/浏览器 Agent（15 工具）
│   │   └── memory_agent.py     # 知识库 Agent（4 工具）
│   │
│   ├── tools/                  # 工具实现
│   │   ├── brain/              # 调度器 / Todo 管理器 / 技能注册
│   │   ├── file/               # 文件操作工具（14 模块）
│   │   ├── code/               # 沙箱执行封装
│   │   ├── web/                # 搜索 / 提取 / 下载 / 浏览器
│   │   └── memory/             # ChromaDB 操作
│   │
│   ├── security/               # 安全模块（4 层防御）
│   │   ├── input_guard.py      # 提示注入检测
│   │   ├── command_guard.py    # 高危命令拦截
│   │   ├── path_safety.py      # 路径安全校验
│   │   └── url_safety.py       # SSRF 防护
│   │
│   ├── sandbox/
│   │   └── bubblewrap.py       # bwrap 沙箱管理器
│   │
│   ├── skills/                 # 可插拔技能文档（Markdown）
│   └── utils/                  # 工具函数 / 异常定义
```

---

## 设计要点

### 多 Agent 协作
Brain Agent 不直接执行操作，而是通过 `dispatcher` 工具将子任务路由给对应子 Agent。每个子 Agent 独立维护 LLM 对话上下文，拥有专属工具集和系统提示词。任务分解由 Brain 的 Todo Manager 驱动，支持进度可视化：

```
[✓] 创建项目目录
[>] 搜索相关资料
[ ] 生成汇总文档
```

### 安全深度防御
四个安全模块在用户输入 → LLM 生成 → 工具执行三阶段各司其职：
1. **输入层**：正则匹配拦截 jailbreak/prompt injection
2. **命令层**：执行前扫描代码/Shell 命令中的危险模式
3. **路径层**：所有文件类工具调用前强制校验（绝对路径 + $HOME 限定 + 敏感目录/文件名黑名单 + 符号链接解析）
4. **网络层**：URL 校验阻塞 SSRF 攻击（内网 IP 段 + localhost）

### 人机协同 (HITL)
对不可逆操作（删除、移动、重命名、文件编辑、下载），系统会弹出确认提示，需要用户在终端输入 `y/n` 方可执行。

---

## 许可证

MIT License

---

## 版本

**v0.2.0** — 毕业设计作品，持续迭代中。
