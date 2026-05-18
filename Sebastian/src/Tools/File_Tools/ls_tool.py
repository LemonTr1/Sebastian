import os
from agents import function_tool
import typer
import json

@function_tool
def ls(path:str):
    """
    列出path路径下所有的文件和目录
    Args:
        path: str类型，表示路径字符串(必须为绝对路径)
    Returns:
        json格式的字符串：
        {
            "success": 表示操作是否成功，成功为True,失败为False
            "file_list": 表示path路径下的所有文件和目录
            "error": 错误信息
        }
    """
    path = os.path.abspath(path)
    typer.echo(typer.style(f"[执行中]正在执行ls {path}", fg=typer.colors.WHITE))
    if not os.path.isdir(path):
        #如果路径不存在或指向文件
        return json.dumps({
            "success": False,
            "file_list": [],
            "error": f"路径错误：{path}不是一个有效的目录"
        }, ensure_ascii=False, indent=2)
    try:
        listed_dir = os.listdir(path) #这里返回list类型
        return json.dumps({
            "success": True,
            "file_list": listed_dir,
            "error": None
        }, ensure_ascii=False, indent=2)
    except PermissionError as e:
        return json.dumps({
            "success": False,
            "file_list": [],
            "error": f"权限错误：没有访问目录{path}的权限：{e}"
        }, ensure_ascii=False, indent=2)
    except OSError as e:
        return json.dumps({
            "success": False,
            "file_list": [],
            "error": f"系统出错：{e}"
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "file_list": [],
            "error": f"未知错误：{e}"
        }, ensure_ascii=False, indent=2)