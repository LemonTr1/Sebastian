from agents import function_tool
import typer
import os
import subprocess

@function_tool
def git_status(repo_path: str)->dict:
    """
    查看 Git 仓库的工作区状态，列出修改、暂存、未跟踪文件。
    Args:
        repo_path: 仓库路径(必须为绝对路径)
    Returns:
        结构化字典，包括success, summary, data字段
    """
    if not os.path.exists(repo_path):
        typer.echo(typer.style(f"[Error]路径不存在：{repo_path} 不存在", fg=typer.colors.RED))
        return {
            "success": False,
            "summary": f"路径不存在：{repo_path} 不存在",
            "data":{}
        }

    try:
        typer.echo(typer.style(f"[执行中]正在获取仓库状态：{repo_path}", fg=typer.colors.WHITE))
        result = subprocess.run(
            ["git", "-C", repo_path, "status", "--porcelain"],
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
                "data":{}
            }

        # 解析输出，构建状态列表
        status_lines = result.stdout.strip().splitlines()
        changes = []
        for line in status_lines:
            status_code = line[:2].strip()
            file_path = line[3:].strip()
            changes.append({"status": status_code, "file": file_path})

        return {
            "success": True,
            "summary": f"成功获取仓库状态，共 {len(changes)} 个变更",
            "data":{"changes": changes}
        }
    except subprocess.TimeoutExpired as e:
        typer.echo(typer.style(f"[Error]执行超时：{e}", fg=typer.colors.RED))
        return {
            "success": False,
            "summary": f"执行超时：{e}",
            "data":{}
        }
    except Exception as e:
        typer.echo(typer.style(f"[Error]执行时发生异常：{e}", fg=typer.colors.RED))
        return {
            "success": False,
            "summary": f"执行时发生异常：{e}",
            "data":{}
        }