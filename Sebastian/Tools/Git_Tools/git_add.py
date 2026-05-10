from agents import function_tool
import typer
import os
import subprocess

@function_tool
def git_add(repo_path: str, paths: str)->dict:
    """
    将文件添加到 Git 仓库的暂存区。
    Args:
        repo_path: 仓库路径(必须为绝对路径)
        paths: 要添加的文件列表（字符串数组，可使用通配符如`["."]`代表全部）
    Returns:
        结构化字典，包括success, summary, data, need_confirmed字段
    """
    repo_path = os.path.abspath(repo_path)
    if not os.path.exists(repo_path):
        typer.echo(typer.style(f"[Error]路径不存在：{repo_path} 不存在", fg=typer.colors.RED))
        return {
            "success": False,
            "summary": f"路径不存在：{repo_path} 不存在",
            "data":{},
            "need_confirmed": False
        }

    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "add"] + paths.split(),
            capture_output=True,
            text=True,
            timeout=30, #设置30s超时时间
            check=False
        )
        if result.returncode != 0:
            typer.echo(typer.style(f"[Error]执行失败：{result.stderr}", fg=typer.colors.RED))
            return {
                "success": False,
                "summary": f"执行失败：{result.stderr}",
                "data":{},
                "need_confirmed": False
            }

        return {
            "success": True,
            "summary": f"成功添加文件到暂存区",
            "data":{},
            "need_confirmed": True
        }
    except subprocess.TimeoutExpired as e:
        typer.echo(typer.style(f"[Error]执行超时：{e}", fg=typer.colors.RED))
        return {
            "success": False,
            "summary": f"执行超时：{e}",
            "data":{},
            "need_confirmed": False
        }
    except Exception as e:
        typer.echo(typer.style(f"[Error]执行时发生异常：{e}", fg=typer.colors.RED))
        return {
            "success": False,
            "summary": f"执行时发生异常：{e}",
            "data":{},
            "need_confirmed": False
        }

