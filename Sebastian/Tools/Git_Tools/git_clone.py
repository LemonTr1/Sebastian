from agents import function_tool
import typer
import os
import subprocess

@function_tool
def git_clone(url: str, local_path: str)->dict:
    """
    克隆远程 Git 仓库到本地指定路径。
    Args:
        url: 远程仓库地址
        local_path：本地目标路径（必须在ALLOW_CLONE_ROOT下）
    Returns:
        结构化字典，包括success, summary, data, need_confirmed字段
    """
    #单独给Agent设置一个本地仓库，防止覆盖原有的工作仓库造成不可逆后果
    ALLOWED_CLONE_ROOT = f"/home/{str(os.getlogin())}/git_agent_workspace"
    #查看本地的克隆仓库是否存在（Git_Agent_Tool绝对不允许独自进行文件操作）
    if not os.path.exists(ALLOWED_CLONE_ROOT):
        typer.echo(typer.style(f"[Warn]路径`{ALLOWED_CLONE_ROOT}`不存在", fg=typer.colors.YELLOW))
        return {
            "success": False,
            "summary": f"不存在路径{ALLOWED_CLONE_ROOT}，请调用File_Agent_Tool创建该目录",
            "data":{},
            "need_confirmed": True
        }

    #路径安全检查
    abs_path = os.path.abspath(local_path)
    if not abs_path.startswith(os.path.abspath(ALLOWED_CLONE_ROOT)):
        typer.echo(typer.style(f"[Error]路径越权：只能克隆到 {ALLOWED_CLONE_ROOT} 下", fg=typer.colors.RED))
        return {
            "success": False,
            "summary": f"路径越权：只能克隆到 {ALLOWED_CLONE_ROOT} 下",
            "data":{},
            "need_confirmed": False
        }

    #检查本地路径是否存在，避免覆盖
    if os.path.exists(abs_path):
        typer.echo(typer.style(f"[Error]路径已存在：{abs_path} 已存在，无法克隆", fg=typer.colors.RED))
        return {
            "success": False,
            "summary": f"路径已存在：{abs_path} 已存在，无法克隆",
            "data":{},
            "need_confirmed": False
        }

    try:
        typer.echo(typer.style(f"[执行中]正在克隆仓库 {url} 到 {abs_path} ...", fg=typer.colors.WHITE))
        result = subprocess.run(
            ["git", "clone", url, abs_path],
            capture_output=True,
            text=True,
            timeout=1200, #考虑GitHub网速问题，设置20分钟足够宽裕的时间
            check=False
        )
    except subprocess.TimeoutExpired as e:
        typer.echo(typer.style(f"[Error]克隆超时：{e}", fg=typer.colors.RED))
        return {
            "success": False,
            "summary": f"错误：克隆超时，请检查网络或仓库大小：{e}",
            "data":{},
            "need_confirmed": False
        }
    except Exception as e:
        typer.echo(typer.style(f"[Error]执行git命令时产生异常：{e}", fg=typer.colors.RED))
        return {
            "success": False,
            "summary": f"执行git命令时产生异常：{e}",
            "data":{},
            "need_confirmed": False
        }

    #如果执行成功
    if result.returncode == 0:
        typer.echo(typer.style(f"[Success]成功克隆仓库到 {abs_path}", fg=typer.colors.GREEN))
        return {
            "success": True,
            "summary": f"成功克隆远程仓库到：{abs_path}",
            "data":{
                "clone_to": abs_path,
                "stdout": result.stdout.strip()
            },
            "need_confirmed": False
        }
    else:
        typer.echo(typer.style(f"[Error]克隆失败：{result.stderr.strip()}", fg=typer.colors.RED))
        return {
            "success": False,
            "summary": f"克隆失败：{result.stderr.strip()}",
            "data":{
                "exit_code": result.returncode,
                "stderr": result.stderr.strip()
            },
            "need_confirmed": False
        }

