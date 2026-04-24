import os
from agents import function_tool

@function_tool
def create_file_with_content(path: str, filename: str, text: str)->bool:
    """
    在path路径下建立新文件，路径错误，路径不存在或建立文件夹失败会返回False，否则返回True
    Args:
        path: 路径字符串
    Returns:
        result: 表示是否建立文件夹成功
    """
    #拼接完整路径
    file_path = os.path.join(path, filename)

    #创建文件并写入
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(text)

    return True
