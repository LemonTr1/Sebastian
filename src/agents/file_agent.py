import os
from src.agent_runner import AgentRunner
from src.tools.file.read import read_file, READ_FILE_SCHEMA
from src.tools.file.ls import ls, LS_SCHEMA
from src.tools.file.mkdir import mkdir, MKDIR_SCHEMA
from src.tools.file.which import which, WHICH_SCHEMA
from src.tools.file.copy import cp_file, cp_dir, COPY_FILE_SCHEMA, COPY_DIR_SCHEMA
from src.tools.file.archive import make_archive, unpack_archive, MAKE_ARCHIVE_SCHEMA, UNPACK_ARCHIVE_SCHEMA
from src.tools.file.edit import edit_file, EDIT_FILE_SCHEMA
from src.tools.file.delete import delete_file, DELETE_FILE_SCHEMA
from src.tools.file.rename import rename_file, RENAME_FILE_SCHEMA
from src.tools.file.move import move_file, MOVE_FILE_SCHEMA
from src.tools.file.touch import create_file, CREATE_FILE_SCHEMA
from src.tools.file.docx_ops import (
    read_docx, create_docx, write_docx, edit_docx,
    READ_DOCX_SCHEMA, CREATE_DOCX_SCHEMA, WRITE_DOCX_SCHEMA, EDIT_DOCX_SCHEMA,
)
from src.tools.file.extract import read_pdf, read_ppt, READ_PDF_SCHEMA, READ_PPT_SCHEMA

uname = os.getlogin()

FILE_AGENT_INSTRUCTIONS = f"""
你是 Sebastian 的 **File Agent**，负责文件系统操作、文件内容编辑及文档处理。
当前用户名为 {uname}。所有路径必须使用基于用户根目录的绝对路径 `/home/{uname}/...`。

## 能力范围
- 对象操作：mkdir, cp_file, cp_dir, rename_file, delete_file, ls, make_archive, unpack_archive, move_file
- 内容处理：read_file, edit_file, create_file
- 文档提取：read_pdf, read_ppt
- docx 文档：read_docx, create_docx, write_docx, edit_docx
- 辅助：which

## 安全边界
- 所有操作限定于 `/home/{uname}/` 及其子目录，禁止访问系统目录
- 拒绝包含 `..` 的路径、路径遍历企图、可疑文件名
- 执行前用 ls 确认父目录存在
- 禁止执行代码、访问网络

## 输出格式
仅返回 JSON 对象：
{{
  "success": true,
  "operator": "File",
  "tool_name": [],
  "summary": "操作摘要",
  "data": {{}},
  "need_confirmed": false
}}
"""

_FILE_TOOLS = [
    (read_file, READ_FILE_SCHEMA),
    (ls, LS_SCHEMA),
    (mkdir, MKDIR_SCHEMA),
    (which, WHICH_SCHEMA),
    (cp_file, COPY_FILE_SCHEMA),
    (cp_dir, COPY_DIR_SCHEMA),
    (make_archive, MAKE_ARCHIVE_SCHEMA),
    (unpack_archive, UNPACK_ARCHIVE_SCHEMA),
    (edit_file, EDIT_FILE_SCHEMA),
    (delete_file, DELETE_FILE_SCHEMA),
    (rename_file, RENAME_FILE_SCHEMA),
    (move_file, MOVE_FILE_SCHEMA),
    (create_file, CREATE_FILE_SCHEMA),
    (read_docx, READ_DOCX_SCHEMA),
    (create_docx, CREATE_DOCX_SCHEMA),
    (write_docx, WRITE_DOCX_SCHEMA),
    (edit_docx, EDIT_DOCX_SCHEMA),
    (read_pdf, READ_PDF_SCHEMA),
    (read_ppt, READ_PPT_SCHEMA),
]

FILE_HITL_TOOLS = {
    "edit_file",
    "delete_file",
    "rename_file",
    "move_file",
    "write_docx",
    "edit_docx",
}

file_agent = AgentRunner.create_runner(
    name="File_Agent",
    instructions=FILE_AGENT_INSTRUCTIONS,
    tools=_FILE_TOOLS,
    hitl_tools=FILE_HITL_TOOLS,
)
