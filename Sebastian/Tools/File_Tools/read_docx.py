import asyncio
import typer
from docx import Document
from agents import function_tool

@function_tool
async def read_docx(file_path: str) -> str:
    """
    读取docx文档的纯文本内容。
    Args:
        file_path: docx文件的完整路径
    Returns:
        成功时返回：文档的纯文本内容
        错误时返回：报错信息
    """
    try:
        typer.echo(typer.style(f"[执行中]正在读取{file_path}文档内容...",fg=typer.colors.WHITE))
        loop = asyncio.get_running_loop()
        doc = await loop.run_in_executor(None, Document, file_path)
        # 收集所有段落的文本
        paragraphs_text = []
        for para in doc.paragraphs:
            if para.text.strip():  # 过滤空段落
                paragraphs_text.append(para.text)
        # 也可以收集表格内容（可选），python-docx 可以方便地遍历表格并将其内容一并返回[reference:0]
        tables_text = []
        for table in doc.tables:
            table_data = []
            for row in table.rows:
                row_data = [cell.text for cell in row.cells]
                table_data.append("\t".join(row_data))
            if table_data:
                tables_text.append("\n".join(table_data))

        # 合并段落和表格内容返回
        full_text = "\n\n".join(paragraphs_text)
        if tables_text:
            full_text += "\n\n【表格内容】\n" + "\n\n".join(tables_text)

        return full_text if full_text else "文档中没有可读取的文本内容。"
    except FileNotFoundError:
        return f"错误：文件不存在 - {file_path}"
    except Exception as e:
        return f"读取文档时出错：{str(e)}"