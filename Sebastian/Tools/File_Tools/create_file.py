import os
import typer
from agents import function_tool

@function_tool
def create_file(path: str, filename: str)->bool:
    """
    在path路径下建立名为filename的新文件，路径错误，路径不存在或建立文件失败会返回False，否则返回True
    Args:
        path: 路径字符串
        filename: 文件名（包含后缀）
    Returns:
        True/False: 表示是否建立文件成功
    """
    #拼接完整路径
    file_path = os.path.join(path, filename)

    if not os.path.exists(path):
        confirmed = typer.confirm(typer.style(f"[Warn]{path}路径不存在，你确定要建立该路径吗", fg=typer.colors.YELLOW))
        if not confirmed:
            typer.echo(f"已终止本次操作")
            return False
        os.makedirs(path, exist_ok=True)
        typer.echo(f"[执行中]文件路径已建立完毕")

    if os.path.exists(file_path):
        confirmed = typer.confirm(typer.style(f"[Warn]文件{filename}已经存在，覆盖会清空内容，确定吗", fg=typer.colors.YELLOW))
        if not confirmed:
            typer.echo("已终止本次操作")
            return False

    with open(file_path, 'w') as f:
        pass

    return True
