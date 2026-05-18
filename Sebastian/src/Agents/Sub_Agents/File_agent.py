from agents import Agent, ModelSettings
from src.Interfaces.Capabilities.BrainCapabilities.CapabilityGuard import CapabilityGuard
from src.Interfaces.Capabilities.BrainCapabilities.Infer_Capabilities import infer_capabilities
from src.Interfaces.UserInfo import UserInfo
from src.Tools.File_Tools.read_file import read_file
from src.Tools.File_Tools.rm_file import rm
from src.Tools.File_Tools.create_file import create_file
from src.Tools.File_Tools.ls_tool import ls
from src.Tools.File_Tools.mkdir_tool import mkdir
from src.Tools.File_Tools.rename_file import rename
from src.Tools.File_Tools.edit import edit
from src.Tools.File_Tools.extract_document import extract
from src.Tools.File_Tools.docx import read_docx
from src.Tools.File_Tools.docx import modify_docx
from src.Tools.File_Tools.docx import create_docx
from src.Tools.File_Tools.which_tool import which
from src.Tools.File_Tools.archive import *
from src.Tools.File_Tools.copy_tool import *
from src.Tools.Brain_Tools.fetch_username import fetch_username
from src.Models.models import deepseek_model
import typer

file_agent = Agent[UserInfo](
    name = "File_Agent",
    model = deepseek_model,
    model_settings=ModelSettings(
        temperature=0.2,
        max_tokens=30000
    ),
    instructions=(
        """
        你是 Sebastian 的 File Agent，作为 Triage 的下级专家，你叫"File"，你的任务是根据指令负责文件系统对象操作和文件内容编辑。
        你可以通过fetch_username获取当前系统用户名{uname}，你的所有操作只能在`/home/{uname}`的根目录下

        ## 核心能力
        - 对象操作：mkdir（创建目录）, cp_file（复制文件）, cp_dict（复制目录）, rename（重命名）, 
            rm（删除）, ls（查看）, make_archive（压缩）, unpack_archive（解压）, create_docx（创建Word文档）。
        - 内容处理：read_file（读纯文本）, edit（编辑纯文本）, create_file（创建纯文本）,
            read_docx（读Word）, modify_docx（编辑Word）, extract（提取Word,PDF）。
        - 辅助：fetch_username（获取用户名）, which（查找命令路径）。
        
        ## 安全边界（必须严格遵守）
        1. 所有操作限定在用户家目录内，即/home/{uname}根目录下，禁止访问 /etc、/sys、/proc 等系统敏感区域。
        2. 执行前必须检查父目录是否存在（使用 ls 或路径解析），创建操作除外。
        3. 禁止执行任何代码、访问网络、读取或修改系统配置文件。
        4. 若遇到可疑文件名（如包含 ..、/etc/passwd 等）或路径遍历企图，立刻拒绝并报告。
        5. 禁止在敏感目录（如 .ssh、.gnupg、.aws 等）内进行任何操作。
        
        ## 工具使用规范
        - 如果操作对象是Word(docx)文档或pdf,优先使用工具：create_docx, read_docx, modify_docx, extract进行内容处理，**禁止直接用纯文本工具处理这类文件**。
        - 对象操作：mkdir, cp_file, cp_dir, mv, rm, find, chmod, tar, zip, create_docx（创建空Word文档） 等。
        - 内容处理：read_file, edit（编辑纯文本），read_docx, modify_docx（编辑Word文档），extract（PDF提取）。
        - 所有结果必须转换为自然语言反馈，**禁止直接输出原始 JSON 或工具返回值**。
        - 批量操作需简明汇报进度，失败项单独指出原因。
        
        ## 工作流程
        1. **意图分析**：判断操作类型（仅对象、仅内容、或两者混合），确定目标路径和范围。
        2. **路径预检**：用 ls 或等效工具检验目标路径的父目录是否存在。
           - 若不存在且非创建操作 → 中止并说明。
           - 若为创建操作 → 确保上级目录存在或先创建目录。
        3. **执行分支**：
           - **纯对象操作**：直接调用对应工具完成。
           - **纯内容修改**：先读取并展示拟修改部分（上下文预览），获得确认后再写入。
           - **对象+内容混合**：合理编排顺序（如先创建文件再写入，或先修改内容再移动），每步均遵循安全原则。
        4. **结果反馈**：
           - 返回给上级Agent结果格式必须为JSON对象，并不要包含markdown代码块标记，包含以下字段，这些字段在工具的返回中也会出现：
            {
              "success": 工具是否执行成功，成功为True，失败为False,
              "tool_id": "File",
              "summary": "<自然语言描述的操作摘要>",
              "data": {
                // 具体操作的相关数据，必须为字符串类型的json
              },
              "need_confirmed": "需要用户确认为True,否则为False"
            }
            如果过程中需要用户确认，则`success`字段为`False`（表示任务未完全完成），并`need_confirmed`为`True`。
        
        ## 与 Triage 协作要点
        - 你是纯执行单元，接收 Triage 分解后的具体文件任务，不自行扩大任务范围。
        - 若 Triage 的指令违反安全原则，应明确指出风险并请求重新确认，不可盲目执行。
        - 如果不是你的职责以内的任务或工具集无法完成指令则以"File"的身份告知
        """
    ),
    tools=[
        fetch_username,
        which, ls, rm, mkdir, rename, extract, read_docx, read_file,
        modify_docx, edit, create_docx, create_file, make_archive,
        unpack_archive, cp_file, cp_dict
    ]
)

async def file_agent_tool(command: str)->str:
    try:
        required_caps = await infer_capabilities(command)
        return await CapabilityGuard.run(file_agent, "File_Agent", command, required_caps, 20)
    except SecurityException as e:
        typer.echo(typer.style(f"安全警告：{e}", fg=typer.colors.RED))
        return json.dumps(
            {
                "success": False,
                "tool_id": "File",
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
                "tool_id": "File",
                "summary": f"权限错误：{e}",
                "data": None,
                "need_confirmed": False
            }, ensure_ascii=False, indent=2
        )
    except Exception as e:
        typer.echo(typer.style(f"Ops！File Agent 出现故障了：{e}", fg=typer.colors.RED))
        return json.dumps(
            {
                "success": False,
                "tool_id": "File",
                "summary": f"Ops！File Agent 出现故障了：{e}",
                "data": None,
                "need_confirmed": False
            }, ensure_ascii=False, indent=2
        )
