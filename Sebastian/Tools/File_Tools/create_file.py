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
        typer.echo(typer.style("[Warn]不存在该路径",fg=typer.colors.YELLOW))

    confirmed = typer.confirm(typer.style(f"[Warn]你确定要建立路径{path}吗（如果路径不存在请谨慎考虑）", fg=typer.colors.RED))
    if not confirmed:
        typer.echo("已终止本次操作")
        return False
    os.makedirs(path, exist_ok=True)

    with open(file_path, 'w') as f:
        pass

    return True
