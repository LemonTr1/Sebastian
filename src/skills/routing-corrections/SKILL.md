---
name: Routing Corrections
description: 常见误判纠正，指导正确使用dispatcher工具（第一次调用dispatcher工具必须查看）。
---
## 常见误判纠正
以下操作**必须走 Web，不要走 Code**——WebAgent 有专用工具：
- "现在几点" / "今天几号" → type="Web"（WebAgent 有 get_current_time_str）
- "搜索 xxx" / "百度一下 xxx" → type="Web"（WebAgent 有 DDGS 结构化搜索）
- "下载 xxx" → type="Web"（WebAgent 有 download_file 带安全扫描）
- "这个网页..." / "这个网站..." → type="Web"（WebAgent 有 web_extract 正文提取）
- "帮我查 GitHub 上..." → type="Web"

以下操作**必须走 File，不要走 Code**——CodeAgent 在沙箱中无法访问宿主机文件：
- "查看 xxx 目录下有什么" / "列出文件" → type="File"（FileAgent 有 ls）
- "读一下 xxx 文件" / "cat xxx" / "head xxx" / "tail xxx" → type="File"（FileAgent 有 read_file）
- "统计 xxx" / "wc -l xxx" → type="File"（先 read_file 读取再让 FileAgent 处理）

以下操作 CodeAgent **做不了**，直接告诉用户手动执行：
- apt install / sudo apt install / yum install 等系统级包管理（需要系统级权限，沙箱做不到）
- curl / wget 获取网络资源（用 WebAgent 替代）

以下用户级包管理操作可直接交给 CodeAgent：
- pip install / npm install（CodeAgent 会映射到宿主机执行）

Code 只管：运行代码文件(.py/.sh/.c/.java)、python3 -c "print(1+1)" 数学计算。