import os
import typer
from agents import function_tool

@function_tool
def create_file_with_content(path: str, filename: str, text: str)->bool:
    """
    在path路径下建立名为filename的新文件，路径错误，路径不存在或建立文件夹失败会返回False，否则返回True
    Args:
        path: 路径字符串
        filename: 文件名（包含后缀）
        text: 文本内容
    Returns:
        result: 表示是否建立文件夹成功
    """
    #拼接完整路径
    file_path = os.path.join(path, filename)

    if not os.path.exists(file_path):
        typer.echo(typer.style("[Warn]不存在目标文件",fg=typer.colors.YELLOW))

    confirmed = typer.confirm(f"你确定要修改{file_path}吗（如果路径不存在请谨慎考虑）")
    if not confirmed:
        typer.echo("已终止本次操作")
        return False

    #创建文件并写入
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(text)

    return True
