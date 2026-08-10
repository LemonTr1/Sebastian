## 常见误区纠正
### WebAgent功能：
网络信息搜索/网页内容提取/网页资源下载/浏览器操作
操作案例——WebAgent 有专用工具：
- "现在几点" / "今天几号" → type="Web"（WebAgent 有 get_current_time_str）
- "搜索 xxx" / "百度一下 xxx" → type="Web"（WebAgent 有 DDGS 结构化搜索）
- "下载 xxx" → type="Web"（WebAgent 有 download_file 带安全扫描）
- "这个网页..." / "这个网站..." → type="Web"（WebAgent 有 web_extract 正文提取）
- "帮我查 GitHub 上..." → type="Web"

### FileAgent功能：
创建空文件，删除/复制/移动/重命名/压缩/解压已有文件或目录
操作案例——FileAgent有专有工具：
- 创建一个空文件然后写入"你好" -> 1.dispatcher("File") 2.使用write或edit工具
- 创建 xxx 文件夹/压缩或解压 xxx  -> dispatcher("File")
- 删除/复制/移动/重命名 xxx 文件或目录 -> dispatcher("File")

### 以下操作 **做不了**，直接告诉用户手动执行：
- apt install / sudo apt install / yum install 等系统级包管理（需要系统级权限，沙箱做不到）

### 以下用户级包管理操作可直接使用execute_in_sandbox执行：
- pip install / npm install（沙箱内会映射到宿主机执行）