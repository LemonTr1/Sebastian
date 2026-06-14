---
name: Code-File协作
description: CodeAgent与FileAgent的协作规范——何时拆为Code+File两步，以及文件持久化禁令。
---
## 铁律：CodeAgent 无法写文件到宿主机
CodeAgent 在 bubblewrap 沙箱中运行，沙箱内所有文件操作对外部不可见。所有文件读写必须通过 FileAgent。

### 禁止行为
- 严禁将持久化路径写入 dispatcher 的 command 参数交给 CodeAgent。CodeAgent 写了也出不了沙箱。
- 严禁将"执行并保存"合并为一次 Code 调用。

### 正确流程
**场景：运行脚本并保存结果**
- 第一步：dispatcher(command="执行 app.py", type="Code") → 获取 stdout
- 第二步：dispatcher(command="将以下内容写入路径：<上一步的data>", type="File")

**场景：用户要求"写一个脚本然后运行它"**
- 第一步：dispatcher(command="创建脚本文件，内容为...", type="File")
- 第二步：dispatcher(command="执行该脚本", type="Code")

注意：向 FileAgent 传递代码/脚本/命令内容时，必须使用 Markdown 代码块包裹（如 ```python\n代码\n```），防止代码中的路径字符串被路径校验误拦截。
