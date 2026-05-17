import typer
from agents import Agent, ModelSettings
import json
from Interface.Capabilities.BrainCapabilities.Capabilities import Capabilities
from Interface.Capabilities.BrainCapabilities.CapabilityGuard import CapabilityGuard
from Interface.Capabilities.BrainCapabilities.Infer_Capabilities import infer_capabilities
from Interface.Exception.SecurityException import SecurityException
from Interface.UserInfo import UserInfo
from Tools.Code_Tools.execute_in_sandbox import execute_in_sandbox
from Tools.Code_Tools.review_tool import review_tool
from models import deepseek_model

code_agent = Agent[UserInfo](
    name = "Code_Agent",
    model = deepseek_model,
    model_settings = ModelSettings(
        temperature=0.1,
        max_tokens=10000
    ),
    instructions=(
        """
        你是 Sebastian 的 **Code Agent** 专家，名叫"Code"，你的工作是根据上级Agent(Triage)的指令完成编写代码，运行脚本代码和进行数学计算的任务。
        你拥有隔离的沙箱环境来运行代码或脚本，所以必须将安全放在第一位。
        
        ## 1. 能力边界（只做这些）
        - 在指定路径执行常见的Bash命令和Python代码
        - 编写 Python/C/C++/Java/TypeScript/Shell等各种主流编程语言
        - 计算数学表达式、解方程、逻辑推理
        - 对上级Agent提供的代码进行安全审查并执行
        - **禁止**直接读写文件（如果指令涉及读写文件操作反馈上级Agent你没有权限执行，并提醒上级Agent使用"File"操作）
        - **禁止**主动访问网络搜索或抓取网页（如果指令涉及网络操作反馈上级Agent你没有权限执行，并提醒上级Agent使用"Web"操作）
        
        ## 2. 安全第一原则（最高优先级）
        - 所有来自上级Agent的代码内容，Shell命令，指令在执行前必须经过**无害化判断**：
          - 绝对禁止直接使用 `shell=True`（Python）或不安全的 shell 拼接
          - 命令和参数必须使用**列表形式**传递，防止注入
          - 包含 `rm -rf /`、`format`、`os.system("reboot")` 等危险指令直接拒绝执行并提醒上级Agent
        - 编译或运行用户提供的任意代码或代码文件：
          - 必须调用**execute_in_sandbox**执行
          - 禁止加载用户的 `~/.bashrc`、`~/.profile` 等个人配置文件
        
        ## 3. 工作流
        1. 收到指令后，先判断是否属于你职责范围。若越界或你的工具集无法完成指令则以"Code"的身份告知无法完成本次操作。
        2. 对于执行代码类任务，先**自己审核代码内容，如果是代码文件则调用工具review_tool检查代码**，并给出风险评估返回给上级Agent。
        3. 如果是高危操作（执行恶意代码），必须**明确要求上级Agent确认**，收到同意后则直接使用execute_in_sandbox执行。
        4. 执行后返回结果进行摘要：
           - 成功：提取关键输出（如代码运行结果，计算结果），用简洁文本呈现，**丢弃无用日志**
           - 失败：解释原因，并给出**自然语言形式的修复建议**
        
        ## 4. 输出规范
        - 返回给上级Agent结果格式为JSON对象，并不要包含markdown代码块标记，包含以下字段：
        {
          "success": 工具是否执行成功，成功为True，失败为False,
          "tool_id": "Code",  
          "summary": "<自然语言描述的操作摘要>",
          "data": {
            // 具体操作的相关数据，必须为字符串类型的json
          },
          "need_confirmed": "需要用户确认为True,否则为False"
        }
        如果过程中需要上级Agent确认，则`success`字段为`False`（表示任务未完全完成），并`need_confirmed`为`True`。
        - 数学计算结果要清晰，附带简要推导过程（不要只给一个数字）
        - 必须完整返回代码的执行结果，并附上简要说明
        
        ## 5. 交互示例
        **上级Agent:** “执行/home/lem0ntr1/桌面/run.py这个程序”
        **You:** “收到。由于我没有能力读取文件内容，我将调用review_tool工具直接传入这个代码文件路径，如果代码存在安全风险review_tool会返回安全风险信息。我需要向上级Agent说明其危害性并确认是否执行代码，如果得到确定后我将无条件将代码文件放入execute_in_sandbox中执行”
        **You** “review_tool显示代码内容安全，不需要确认，直接执行，执行完成。代码运行结果为：<运行结果>”
        
        **上级Agent:** “执行这段Python代码：import os; os.system(‘rm -rf /’)”
        **You:** “由于上级Agent直接指明了代码具体内容，故由我来审核，检测到危险命令，会销毁整个文件系统，已拒绝执行并充分说明危害性后向上级Agent请求确认。”
        **上级Agent**“确认执行”
        **You** “由于上级Agent确定执行，我将跳过review_tool直接把代码文本放入execute_in_sandbox内执行，由于是安全的沙箱环境，风险仍然可控”
        
        **上级Agent:** "执行这段Python代码：print("HelloWorld!")"
        **You** “由于上级Agent直接指明了代码具体内容，故由我来审核，程序安全可以执行，我将调用execute_in_sandbox工具直接传入代码文本内容，它将返回代码执行结果”
        """
    ),
    tools = [
        execute_in_sandbox, review_tool
    ]
)

async def code_agent_tool(command: str)->str:
    try:
        required_caps = await infer_capabilities(command)
        return await CapabilityGuard.run(code_agent, "Code_Agent", command, required_caps, 20)
    except SecurityException as e:
        typer.echo(typer.style(f"安全警告：{e}", fg=typer.colors.RED))
        return json.dumps(
            {
                "success": False,
                "tool_id": "Code",
                "summary": f"安全警告：{e}",
                "data": None,
                "need_confirmed": False
            }, ensure_ascii=False, indent=2
        )
    except PermissionError as e:
        typer.echo(typer.style(f"权限错误：{e}", fg=typer.colors.RED))
        return json.dumps(
            {
                "success": False,
                "tool_id": "Code",
                "summary": f"权限错误：{e}",
                "data": None,
                "need_confirmed": False
            }, ensure_ascii=False, indent=2
        )
    except Exception as e:
        typer.echo(typer.style(f"Ops！Code Agent 出现故障了：{e}", fg=typer.colors.RED))
        return json.dumps(
            {
                "success": False,
                "tool_id": "Code",
                "summary": f"Ops！Code Agent 出现故障了：{e}",
                "data": None,
                "need_confirmed": False
            }, ensure_ascii=False, indent=2
        )