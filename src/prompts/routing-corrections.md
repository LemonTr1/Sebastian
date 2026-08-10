## 常见误区纠正
### WebAgent功能：
网络信息搜索/网页内容提取/网页资源下载/浏览器操作
操作案例——WebAgent 有专用工具：
- "搜索 xxx" / "百度一下 xxx" → type="Web"（WebAgent 有 DDGS 结构化搜索）
- "下载 xxx" → type="Web"（WebAgent 有 download_file 带安全扫描）
- "这个网页..." / "这个网站..." → type="Web"（WebAgent 有 web_extract 正文提取）
- "帮我查 GitHub 上..." → type="Web"

### FileAgent功能（工具在 src/tools/file/ 下）：
创建空文件，删除/复制/移动/重命名/压缩/解压已有文件或目录

#### Brain 自持工具 vs FileAgent 工具分工表（基于源码）：

| 操作 | 正确工具 | 源码依据 / 说明 |
|------|---------|----------------|
| **新建文件** | `dispatcher("File")` → `create_file` | Brain 的 `write` **不支持创建**（文件不存在直接报错）；`create_file` 专为创建而生 |
| **覆盖已有文件** | Brain：先 `read_file` 看原内容 → 再 `write`/`edit` | `write` 是无条件 `"w"` 全量覆盖，无原内容保护；`edit` 有 `old_text` 匹配兜底更安全 |
| **删除文件/目录** | `dispatcher("File")` → `delete_file` | 不可逆，需 HITL 确认 |
| **移动/重命名** | `dispatcher("File")` → `move_file` / `rename_file` | 需 HITL 确认 |
| **复制** | `dispatcher("File")` → `cp_file` / `cp_dir` | — |
| **创建目录** | `dispatcher("File")` → `mkdir` | — |
| **压缩/解压** | `dispatcher("File")` → `make_archive` / `unpack_archive` | 支持 zip/tar/gz/bz2/xz/7z，解压有路径遍历防护 |
| **读文件** | Brain：`read_file` | offset/limit 必须成对 |
| **搜索** | Brain：`grep` / `glob` / `ls` | — |
| **写脚本后运行** | ① `dispatcher("File")` 创建 → ② `execute_in_sandbox` 运行 | — |

关键点：
- Brain 的 `write` **不能创建文件**，新建一律走 `dispatcher("File")`
- `write` 覆盖已有文件前，**必须先 `read_file` 确认原内容**，避免静默清空
- 删除/移动类操作**不可逆或破坏性大**，交给 FileAgent（带 HITL 确认），Brain 不自持这些工具

操作案例——FileAgent有专有工具：
- 创建一个空文件然后写入"你好" -> 1.dispatcher("File") 2.使用write或edit工具
- 创建 xxx 文件夹/压缩或解压 xxx  -> dispatcher("File")
- 删除/复制/移动/重命名 xxx 文件或目录 -> dispatcher("File")

### 以下用户级包管理操作可直接使用execute_in_sandbox执行：
- pip install / npm install（沙箱内会映射到宿主机执行）