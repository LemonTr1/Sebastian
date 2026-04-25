import typer
import os
from agents import function_tool

@function_tool
def edit(path: str, filename: str, context: str)->bool:
    """
    编辑/修改文件内容，如果修改文件内容成功返回True，否则返回False
    Args:
        path: 路径字符串
        filename: 文件名（包含后缀）
        context: 待写入的文本内容（会覆盖掉原来的文本内容）
    Returns:
        True/False: 表示是否修改成功
    """
    file_path = os.path.join(path, filename)
    confirmed = typer.confirm(typer.style(f"[Warn]你确定要修改文件{file_path}的内容吗", fg=typer.colors.RED))
    if not confirmed:
        typer.echo("已终止本次操作")
        return False
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(context)
    return True

