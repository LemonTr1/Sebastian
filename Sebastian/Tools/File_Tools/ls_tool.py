import os
from agents import function_tool

@function_tool
def ls(path:str):
    """
    列出path路径下所有的文件和目录
    Args:
        path: 路径字符串
    Returns:
        file_list: path路径下的所有文件和目录
        None: 路径不存在或不是一个目录
    """
    if not os.path.isdir(path):
        return None
    try:
        return os.listdir(path) #这里返回list类型
    except (PermissionError, FileNotFoundError, OSError):
        return None