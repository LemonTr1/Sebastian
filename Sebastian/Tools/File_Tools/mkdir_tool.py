import os
from agents import function_tool

@function_tool
def mkdir(path: str)->bool:
    """
    在path路径下建立新文件夹，路径错误，路径不存在或建立文件夹失败会返回False，否则返回True
    Args:
        path: 路径字符串
    Returns:
        result: 表示是否建立文件夹成功
    """