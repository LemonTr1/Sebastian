import typer
import os
from agents import function_tool

@function_tool
def edit(path: str, filename: str, context: str)->str:
    """
    编辑/修改文件内容
    Args:
        path: 父目录路径字符串
        filename: 文件名（包含扩展名）
        context: 待写入的文本内容（会覆盖掉原来的文本内容）
    Returns:
        修改成功返回：“修改文件内容成功”
        修改失败返回：“用户已终止本次操作”
    """
    file_path = os.path.join(path, filename)
    confirmed = typer.confirm(typer.style(f"[Warn]你确定要修改文件{file_path}的内容吗", fg=typer.colors.YELLOW))
    if not confirmed:
        typer.echo("已终止本次操作")
        return f"用户已终止本次操作"
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(context)
    return f"修改文件内容成功"

