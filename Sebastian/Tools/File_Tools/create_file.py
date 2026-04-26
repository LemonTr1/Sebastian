import os
import typer
from agents import function_tool

@function_tool
def create_file(path: str, filename: str)->bool:
    """
    在path路径下建立名为filename的空文件，路径错误
    如果目录不存在，询问用户是否创建；如果文件已存在，询问是否覆盖（清空内容）
    Args:
        path: 路径字符串
        filename: 文件名（包含后缀）
    Returns:
        True: 文件创建成功（新建或覆盖已有文件）
        False: 用户取消操作，或目录/文件创建失败
    """
    #拼接完整路径
    file_path = os.path.join(path, filename)

    if not os.path.exists(path):
        confirmed = typer.confirm(typer.style(f"[Warn]{path}路径不存在，你确定要建立该路径吗", fg=typer.colors.YELLOW))
        if not confirmed:
            typer.echo(f"已终止本次操作")
            return False
        try:
            os.makedirs(path, exist_ok=True)
            typer.echo(f"[执行中]文件路径{path}已创建")
        except OSError as e:
            typer.echo(typer.style(f"[Error]创建路径{path}失败:{e}",fg=typer.colors.RED))
            return False

    if os.path.exists(file_path):
        confirmed = typer.confirm(typer.style(f"[Warn]文件{file_path}已经存在，覆盖会清空内容，确定吗", fg=typer.colors.YELLOW))
        if not confirmed:
            typer.echo("已终止本次操作")
            return False

    try:
        #创建空文件
        with open(file_path, 'w') as f:
            pass
        typer.echo(f"[执行中]文件{file_path}已创建/覆盖")
        return True
    except OSError as e:
        typer.echo(typer.style(f"[Error] 创建文件 {file_path} 失败: {e}", fg=typer.colors.RED))
        return False

