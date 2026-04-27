from docx import Document
from agents import function_tool
import typer

@function_tool
async def modify_docx(
        file_path: str,
        new_content: str,
        mode: str = "append"
) -> str:
    """
    修改 docx 文档的内容。
    Args:
        file_path: docx 文件的完整路径
        new_content: 要添加或替换的内容
        mode: 操作模式 —— "append"（追加到末尾）、"replace"（全局替换文本）
    Returns:
        操作结果说明
    """
    typer.echo(typer.style(f"[执行中]正在修改docx文档内容", fg=typer.colors.WHITE))

    try:
        doc = Document(file_path)
        if mode == "append":
            doc.add_paragraph(new_content)
        elif mode == "replace":
            for paragraph in doc.paragraphs:
                if new_content in paragraph.text:
                    # 注意：直接替换段落文本会丢失样式
                    paragraph.text = paragraph.text.replace(new_content, new_content)
        else:
            raise ValueError(f"不支持的 mode: {mode}")

        confirmed = typer.confirm(
            typer.style(f"[Warn]是否要保存对{file_path}的修改吗？", fg=typer.colors.YELLOW)
        )
        if not confirmed:
            typer.echo("操作已终止")
            return "操作已取消，文件未保存"

        doc.save(file_path)
        return f"成功修改文档：{mode} 模式已完成。"

    except FileNotFoundError:
        return f"错误：文件不存在 - {file_path}"
    except Exception as e:
        return f"修改文档时出错：{str(e)}"