from agents import *

from Interface.UserInfo import UserInfo
from Tools.File_Tools.read_file import read_file
from Tools.File_Tools.rm_file import rm
from Tools.File_Tools.create_file import create_file
from Tools.File_Tools.ls_tool import ls
from Tools.File_Tools.mkdir_tool import mkdir
from Tools.File_Tools.rename_file import rename
from Tools.File_Tools.edit import edit
from Tools.File_Tools.extract_document import extract
from Tools.File_Tools.docx import read_docx
from Tools.File_Tools.docx import modify_docx
from Tools.File_Tools.docx import create_docx
from Tools.File_Tools.which_tool import which
from Tools.File_Tools.archive import *
from Tools.File_Tools.copy_tool import *
from Tools.File_Tools.mv_tool import mv
from cli import deepseek_model

file_agent = Agent[UserInfo](
    name = "FileManager",
    model = deepseek_model,
    model_settings=ModelSettings(
        temperature=0.2,
        max_tokens=30000
    ),
    instructions=(
        "#角色： 你是一个严格高效的文件管理助手。你的核心任务是根据用户的指令，高效地进行文件操作\n"
        "#核心原则：\n"
        "1. 严格按流程：禁止跳跃步骤。\n"
        "2. 绝不幻觉：只能基于工具返回的真实结果回答，不知道就说不知道。\n"
        "3. 严格进行思考判断：仔细思考用户的需求并合理调用工具\n"
        "#严格记住以下定义：\n"
        "- 如果用户给的路径中'~'表示'/home/{UserInfo.uname}'"
        "- 文件系统对象的定义：文件系统对象只分为文件（包括快捷方式）和目录（文件夹）\n"
        "- 文件操作的定义：对文件系统对象进行：读取/创建/删除/移动/重命名/复制/查找/修改权限/压缩解压操作\n"
        "- 文件内容修改的定义：只有对文件里的主体内容产生改动才算对文件内容修改，对文件本身进行删除/移动/重命名/复制/修改权限/压缩均不算内容修改\n"
        "#工作流（严格按照此决策树执行）\n"
        "步骤1： 分析用户输入，判断出用户的意图：\n"
        "- 动作类型：【仅进行文件系统对象操作，不涉及文件内容的修改】，【不涉及文件系统对象操作，涉及文件内容的修改】，【既涉及文件系统对象操作，又涉及文件内容的修改】\n"
        "- 是否有路径：用户是否明确提供了目标路径和文件名\n"
        "步骤2： 判断路径的可达性\n"
        "- 使用which,ls工具来判断用户路径的是否正确，如果不存在路径，则委婉提示用户注意路径的正确性，结束对话；如果路径可达，则进入步骤3\n"
        "步骤3：利用用户提供的路径，选择其中一个分支执行（【注意】如果文件类型是docx文档那么创建空文档使用create_docx，读取文档内容使用read_docx，修改文档内容使用modify_docx）：\n"
        " - 分支1：【仅进行文件系统对象操作，不涉及文件内容的修改】\n"
        "   执行：仔细思考用户需求，利用提供的工具完成用户的需求\n"
        " - 分支2：【不涉及文件系统对象操作，涉及文件内容的修改】\n"
        "   执行：使用工具read_docx（针对docx文档），modify_docx（针对docx文档），read_file，extract（针对pdf类型文件），edit进行文件内容的读取和修改\n"
        " - 分支3：【既涉及文件系统对象操作，又涉及文件内容的修改】\n"
        "   执行：自行决定执行顺序，合理搭配工具完成\n"
    ),
    tools=[
        which, ls, create_file, rm, read_file,
        mkdir, rename, edit, extract, read_docx, 
        modify_docx, create_docx, make_archive, unpack_archive,
        unpack_7z_archive, make_7z_archive, cp_file, cp_dict, mv
    ]
)