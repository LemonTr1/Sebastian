from docx import Document
from agents import function_tool
import typer

@function_tool
async def create_docx(file_path: str) -> str:
    """
    在指定路径创建一个全新的空白 .docx 文档。
    该文档不包含任何预设内容（无标题、无段落），
    可被 LibreOffice 和 Microsoft Office 正常打开。
    Args:
        file_path: 要创建的 .docx 文件的完整路径
    Returns:
        操作结果说明（成功或失败）
    """
    try:
        confirmed = typer.confirm(typer.style(f"[Warn]确定创建/覆盖文档{file_path}吗？",fg=typer.colors.YELLOW))
        if not confirmed:
            typer.echo("已终止此操作")
            return f"用户阻止了本次操作"
        # 创建一个空白的 Document 对象
        doc = Document()
        # 直接保存，不添加任何内容
        doc.save(file_path)
        typer.echo(typer.style(f"{file_path}已创建", fg=typer.colors.WHITE))
        return f"成功创建空白文档：{file_path}"
    except Exception as e:
        return f"创建失败：{str(e)}"