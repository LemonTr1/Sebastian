---
name: 路径与代码块安全
description: 路径格式规范与代码块包裹规则——防止路径字符串被安全校验误拦截。
---
## 路径格式铁律
- 所有路径必须使用绝对路径格式 `/home/{uname}/...`
- 禁止使用：相对路径 `./foo`、`~` 简写、`$HOME` 变量、`..`
- 用户给出的非规范路径（`~`、`..`、符号链接），必须先规范化为 `/home/{uname}/...` 格式

## 代码块包裹规则
dispatcher 的 command 参数会被路径安全校验扫描。为避免代码/Shell命令中的路径字符串被误判为非法路径，必须使用 Markdown 代码块包裹：
- 向 CodeAgent 传递命令时：dispatcher(command="执行如下代码：\n```shell\nls -la /workspace/\n```", type="Code")
- 向 FileAgent 传递脚本内容时：dispatcher(command="创建文件，内容为：\n```python\nimport os\nprint(os.getcwd())\n```", type="File")

## only_path 挂载规则（仅 Code 类型）
- 仅挂载代码执行所需的**单个最小路径**
- 独立脚本挂载文件本身，项目挂载目录
- 禁止挂载：用户根目录、桌面、.ssh、.gnupg 等敏感目录
- 纯计算/不涉及文件读写 → 传空字符串 ""
