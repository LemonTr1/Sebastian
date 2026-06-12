---
name: 文档处理
description: 处理各种文档格式（如 docx、pdf、pptx）的创建、读取、编辑和写入。
---
## 文档处理技能涵盖了对各种文档格式的处理能力，主要包括 docx、pdf 和 pptx 文件。以下是每种文档类型的处理方式和示例：
- **docx 文件**：创建、读取、编辑、写入 docx **必须路由到 File（type="File"）**。
  FileAgent 拥有 create_docx/read_docx/write_docx/edit_docx 专用工具，可完整处理 docx 文档。
  示例：
  - "帮我创建一个关于项目计划的 docx 文档" → dispatcher(command="创建 /home/{uname}/文档/project.docx...", type="File")
  - "读取 report.docx 的内容" → dispatcher(command="读取 /home/{uname}/report.docx", type="File")
  - "把 contract.docx 里的甲方替换成XX公司" → dispatcher(command="编辑 /home/{uname}/contract.docx 查找替换...", type="File")
- **pdf 文件**：提取/阅读 pdf 内容 **必须路由到 File（type="File"）**。
  FileAgent 拥有 read_pdf 工具可提取 PDF 全部文本和表格。创建/编辑 pdf 暂不支持。
  示例：
  - "帮我看看这个 PDF 里写了什么" → dispatcher(command="提取 /home/{uname}/report.pdf 的内容", type="File")
  - "下载这个 PDF" → dispatcher(command="下载 https://example.com/doc.pdf 到 /home/{uname}/下载/", type="Web")
- **ppt/pptx 文件**：提取/阅读 ppt 内容 **必须路由到 File（type="File"）**。
  FileAgent 拥有 read_ppt 工具可提取幻灯片文本（仅支持 .pptx 格式）。
  示例：
  - "这个 PPT 讲了什么" → dispatcher(command="提取 /home/{uname}/slides.pptx 的幻灯片内容", type="File")
- 以上 pdf/docx/pptx 均**必须路由到 FileAgent（type="File"）**，CodeAgent 无法处理二进制文档格式