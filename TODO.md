# TODO：终端唯一 HITL + 提示符重绘（已实现）

> 状态：v4 已实现（2026-10-30）  
> 目标：去掉 Tkinter / DISPLAY / `python3-tk` 依赖，让审批、提问、REPL 在纯终端下不被后台日志冲散。  
> 范围：只做视觉层重绘 + 现有输入锁；没有引入 ApprovalQueue / OutputBroker。

## 0. 实现结果

- [x] 新增 `src/utils/ui_redraw.py`
- [x] 重写 `src/utils/interaction.py` 为纯终端实现
- [x] HITL 改为 `terminal_confirm()`，传入来源 Agent
- [x] `question` 工具改为 `terminal_question()`
- [x] REPL `read_user_message()` 改用 `gated_input()`
- [x] 流式 token 改为按行 `emit_token()`
- [x] 后台/cron 输出通过 `typer.echo` 代理进入 `ui_redraw`
- [x] 审批/提问整块 header 与输入行一起重绘，去掉锁外 `[HITL]` 行
- [x] 流式尾行在 brain/cron/工具调用前 flush
- [x] 流式 Markdown 行级渲染（标题/粗体/斜体/行内代码/列表/引用/代码块）
- [x] 删除 Tk 文件、GUI 客户端、GUI 测试
- [x] 删除 `src/eval/`、`eval_flag.py`、eval 测试与引用
- [x] README / README_EN / requirements 删除 Tk/eval 说明
- [x] 全量测试通过（42 个测试文件）

## 1. 为什么不是“加锁”

终端里不存在 OS 级的“输入行”。`input()` 等待时，提示符和半截输入只是 readline 画在屏幕上的“颜料”，stdin 是字节流。因此不能“保护输入行”，只能**重画**。

现有输入串行化已经由 `TERMINAL_IO_LOCK` 提供：

- `read_user_message()` 持锁
- `terminal_confirm()` 持锁
- `terminal_question()` 持锁

后到审批会等待；本次只解决“当前提示符被日志冲散”的视觉问题。

## 2. 重绘协议

异步日志到达时：

1. `readline.get_line_buffer()` 取半截输入；
2. `\r\x1b[2K` 擦掉整行；
3. 打印日志 + 换行；
4. 重写“提示符 + 半截输入”；
5. 全程持 `_write_lock`，合成一次 `write()`。

实测字节序列：

```text
是否允许？[y/N] y\r\x1b[2K[BG] first log\r\n是否允许？[y/N] y
```

`readline` 感知不到重绘，因为屏幕结果与它的内部状态一致。

## 3. 关键实现

### 3.1 `ui_redraw`

- `gated_input(prompt, timeout=None)`：登记当前提示符，调用原生 `input()`；超时抛 `InputTimeout`。
- `emit(text, agent=None, nl=True)`：有活跃提示符且来自其他线程时走擦行/重画；否则走原始 `typer.echo`。
- `emit_token(agent, token)`：按完整行提交，避免每个 token 触发重绘。
- `install()` / `uninstall()`：替换/恢复 `typer.echo`；幂等。
- `_active_prompt` 记录提示符文本、属主线程；只对异线程输出重绘。

### 3.2 `interaction`

- `terminal_confirm()`：打印工具名、来源 Agent、参数；`gated_input("是否允许？[y/N] ")`；默认拒绝。
- `terminal_question()`：打印问题与选项，支持编号/自由文本；超时/取消返回结构化状态。
- `sanitize()`：打印前去除 ANSI/控制字符，防终端注入。
- 不再有 `gui_available`、`SEBASTIAN_INTERACTION`、Tk 子进程。

### 3.3 CLI

- `_run_chat()` 启动时 `ui_redraw.install()`。
- `read_user_message()` 用 `gated_input`，保留 `TERMINAL_IO_LOCK` 与 `_stdin_pending` 多行拼接。
- 主 Brain / cron 的 `on_token` 改为 `ui_redraw.emit_token(...)`。

### 3.4 后台输出

`typer.echo` 被代理到 `ui_redraw`，因此 `agent_runner`、`cron_schedule`、`question` 等现有 `typer.echo` 自动接入；未直接改每个调用点。

## 4. 已删除

- `src/utils/approval_client.py`
- `src/utils/question_client.py`
- `src/utils/approval_dialog.py`
- `src/utils/question_dialog.py`
- `src/utils/dialog_common.py`
- `test/test_approval_client.py`
- `src/eval/`（含 cases/results/README）
- `src/utils/eval_flag.py`
- `test/test_eval_checkers.py`
- `test/test_eval_harness.py`
- README 中 Tk / `python3-tk` / `SEBASTIAN_INTERACTION` / Eval 模式说明
- `requirements.txt` 中的 `python3-tk` 注释

## 5. 验证

### 单元测试

- `test/test_ui_redraw.py`：10 项通过（擦行重绘、半截输入、emit/token 缓冲）。
- `test/test_interaction.py`：24 项通过。
- `test/test_question_tool.py`：8 项通过。
- `test/test_agent_mode.py`：21 项通过。
- 全量 `python test/run_all.py`：42 个测试文件通过。

### PTY 实测

- 输入半截 `y` 时后台日志插入：出现 `\r\x1b[2K`，日志后提示符与 `y` 原样恢复。
- `terminal_confirm("bash", ..., agent_name="CodeWriter")`：审批块、来源、两条后台日志、最终 `True` 均正确。
- 管道/非 TTY：`gated_input` 直通原生 `input`；`terminal_confirm` 默认拒绝。

## 6. 已知限制

- **单行提示符**：超长自动换行的输入行/块不保证重绘正确；普通审批/提问无影响。
- **Markdown**：表格按原样显示；跨行粗体/斜体不保证完整渲染；代码块不做语法高亮。
- **光标位置**：重画后光标在行尾；方向键移到行中会跳回。
- **高频日志**：目前按完整行重绘，未做 50ms 合并；极端刷屏可能闪烁。
- **`terminal_question`**：用 `gated_input` 读取，半截输入可重绘；但超时只在开始等待前检查，用户开始输入后不再强制超时。
- **直接 fd 写入**：后台进程若直接继承终端 fd，绕过 Python 门闸；后台 bash 当前捕获-回放，符合约束。
- **多审批排队**：后到者等待现有 `TERMINAL_IO_LOCK`，没有队列位次/来源列表；只显示当前来源 Agent。

## 7. 后续可选

- [ ] 高频日志 50ms 合并，减少闪烁。
- [ ] 审批队列：显示 `[1/3] Agent` 与排队位次。
- [ ] 多行提示符/复杂光标编辑：升级 `prompt_toolkit.patch_stdout`。
- [ ] 给后到审批一个“正在等待”的轻量提示。

## 8. 关键文件

- `src/utils/ui_redraw.py`
- `src/utils/interaction.py`
- `cli.py` 的 `read_user_message` / `_run_chat` / `on_token`
- `src/hooks/pre_tool_use/02_hitl_hook.py`
- `src/tools/toolkits/question.py`
- `src/agent_runner.py`、`src/tools/toolkits/cron_schedule.py`（通过 `typer.echo` 代理接入）
