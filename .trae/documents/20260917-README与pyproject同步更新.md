# 计划：同步更新 README.md 与 pyproject.toml

## 摘要
完整阅读项目后，发现 README.md 与代码实际存在多处偏差（新增 `view_image` 工具、依赖由 4 个增至 8 个、web_search/web_fetch 降级逻辑未文档化、版本号冲突）。本次将 README.md 与 pyproject.toml 一并修正，使其与代码现状一致；版本号统一为 **1.0.0**。

## 当前状态分析（核实结论）

### 工具现状
实际注册到 `Brain_Agent` 的工具共 **16 项**，README 仅列 15 项，缺：
- **`view_image`**（`src/tools/toolkits/view_image.py`）：读取本地图片（png/jpg/jpeg/webp/gif/bmp），以 OpenAI 多模态 content 形式返回给视觉模型查看，大小上限 15MB，非 HITL，仅 Brain_Agent 可用。注册于该文件 line 89。

### 依赖现状
- `requirements.txt` 现有 **8 个** pip 依赖：typer、openai、python-dotenv、ddgs、**baidusearch**、**requests**、**beautifulsoup4**、**lxml**（后 4 个为最近为降级新增）
- `pyproject.toml` `dependencies` 仍只有 4 个（typer、openai、python-dotenv、ddgs），**缺少降级依赖**，导致 `pip install -e .` 安装后 Baidu/Bs4 降级不可用
- 降级逻辑代码佐证：
  - `web_search`：DDGS 失败降级百度（`src/tools/toolkits/web_search.py`）
  - `web_fetch`：DDGS 失败降级 requests+BeautifulSoup/lxml（`src/tools/toolkits/web_fetch.py`）

### 版本冲突
- 顶端徽章 `v0.2.0`、README 底部 `v1.0.0`、pyproject `version="0.2.0"`
- 决策：统一为 **1.0.0**

## 变更内容

### 1. `pyproject.toml`
- `version = "0.2.0"` → `version = "1.0.0"`
- `dependencies` 补充：
  - `baidusearch>=1.0`
  - `requests>=2.31`
  - `beautifulsoup4>=4.12`
  - `lxml>=5.0`

### 2. `README.md`（中文版）
| 位置 | 现状 | 改为 |
|------|------|------|
| L9 徽章 | `v0.2.0` | `v1.0.0` |
| L154 「全部 15 项」 | 15 项 | 16 项 |
| 工具表（L156-172） | 15 行，缺 view_image | 新增一行 `view_image`（非 HITL）：读取本地图片（png/jpg/jpeg/webp/gif/bmp）供视觉模型查看（≤15MB） |
| L165 web_search 说明 | 「DuckDuckGo 网页搜索（超时保护）」 | 补充「DDGS 失败降级百度搜索」 |
| L166 web_fetch 说明 | 「网页正文提取（请求前 SSRF 检查）」 | 补充「DDGS 失败降级 requests+BeautifulSoup」 |
| L382 项目结构「15项工具实现」 | 15 项 | 16 项；`toolkits/` 注释下补充 `view_image.py` 条目 |
| L454 技术栈-网页搜索 | `DuckDuckGo（ddgs）` | 增补「百度搜索（baidusearch）降级」；并补充正文提取行 `requests + beautifulsoup4 + lxml` |
| L458 依赖控制原则 | 「仅保留 4 个 pip 依赖（typer、openai、python-dotenv、ddgs），安装体积约 50MB」 | 更新为实际 8 个依赖的说明（typer、openai、python-dotenv、ddgs、baidusearch、requests、beautifulsoup4、lxml），并注明「网页搜索/正文提取的降级依赖」定位 |
| L468 底部「v1.0.0」 | 已正确 | 保持 |

> 说明：L458 中的「安装体积约 50MB」需结合新增依赖重估，因无法精确统计，改写为「核心依赖保持精简，网页抓取与降级依赖按需内置」等不依赖具体体积的表述，或更新体积描述。

### 不改动项（本次范围外）
- `README_EN.md`：不在本次范围，但 README.md 内联「[English](README_EN.md)」链接保留
- 其他代码文件（仅 pyproject 依赖与 README 文案）

## 假设与决策
- 版本以 README 底部的 v1.0.0 为准，同时提升 pyproject version 与徽章
- `view_image` 为非 HITL 工具，工具表 HITL 列为空
- README_EN.md 不同步（用户仅要求 README.md + pyproject.toml）

## 验证步骤
1. `python -m py_compile pyproject.toml` 不适用（非 Python）；改用 `.venv/bin/python -c "import tomllib; tomllib.load(open('pyproject.toml','rb'))"` 校验 TOML 合法性
2. 检查 README 中不再残留「15 项」「4 个 pip 依赖」「v0.2.0」等过期文案：`grep -n "15 项\|4 个 pip\|v0.2.0" README.md`
3. 确认工具表含 view_image 且计数为 16
4. `pip install -e .`（可选）验证未安装降级依赖时报错不再出现