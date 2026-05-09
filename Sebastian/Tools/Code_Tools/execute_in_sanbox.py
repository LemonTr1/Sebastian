from typing import List, Optional
from agents import function_tool
from Interface.BubblewrapExecutor import BubblewrapExecutor
import re
import os
from pathlib import Path
import typer

HOME = str(Path.home())

@function_tool
def bash(command: str, allowed_dir: str, allow_network: bool = False, extra_ro_binds: Optional[List[str]] = None) -> dict:
    """
    在隔离的沙箱环境中执行一条 Shell 命令。
    Args:
        command: Shell命令
        allowed_dir: 允许读写的目录（会被可读写挂载），必须位于 /home/{uname}/ 下
        allow_network: 是否允许网络访问（默认 False）
        extra_ro_binds: 额外只读挂载的文件或目录，用于暴露沙箱外资源。
                       推荐用法：
                       - Docker命令：extra_ro_binds=["/var/run/docker.sock"]，且 allow_network=True
                       - NVIDIA GPU：extra_ro_binds=["/dev/nvidia0", "/dev/nvidiactl", "/dev/nvidia-modeset",
                                           "/dev/nvidia-uvm", "/usr/lib/x86_64-linux-gnu/libcuda*"]
                       - 第三方库（conda等）：extra_ro_binds=["/opt/conda", "/usr/local/lib"]
                       若命令失败，返回结果中会包含 suggested_extra_ro_binds 字段，请按建议重试。
    Returns:
        结构化字典，包含 success, error, details, stdout, stderr, suggested_extra_ro_binds 等字段
    """
    abs_path = os.path.abspath(allowed_dir)
    if not Path(abs_path).is_relative_to(Path(HOME)):
        typer.echo(typer.style(f"[Error]安全限制：只能访问用户主目录下的路径:{HOME}，禁止访问 {abs_path}", fg=typer.colors.RED))
        return {"success": False, "error": "安全限制", "details": f"只能访问当前用户主目录下的路径，禁止访问 {abs_path}"}
    typer.echo(typer.style(f"[执行中]正在隔离的{abs_path}目录下执行Shell命令：{command[:20]}，网络访问权限：{'允许' if allow_network else '禁止'}",fg=typer.colors.WHITE))
    executor = BubblewrapExecutor(
        allowed_dir=abs_path,
        allow_network=allow_network,
        extra_ro_binds=extra_ro_binds
    )

    try:
        result = executor.run(command, "shell")
    except TimeoutError as e:
        typer.echo(typer.style(f"[Error]命令执行超时：{str(e)}", fg=typer.colors.RED))
        return {"success": False, "error": "命令执行超时", "details": str(e)}
    except RuntimeError as e:
        typer.echo(typer.style(f"[Error]命令执行失败：{str(e)}", fg=typer.colors.RED))
        return {"success": False, "error": "命令执行失败", "details": str(e)}
    except Exception as e:
        typer.echo(typer.style(f"[Error]未知错误：{str(e)}", fg=typer.colors.RED))
        return {"success": False, "error": "未知错误", "details": str(e)}

        # ---- 新增：分析 stderr，推断缺失的只读绑定 ----
    suggested_binds = []
    stderr_text = result.stderr or ""
    stdout_text = result.stdout or ""

    # 匹配动态库缺失： "error while loading shared libraries: libXXX.so: cannot open shared object file"
    match = re.search(r"error while loading shared libraries: (.+?):", stderr_text)
    if match:
        lib = match.group(1)
        # 尝试用 ldconfig 或 find 查找，但沙箱内可能没有这些工具；更稳健的做法是提示用户挂载整个 /usr/lib 相关目录
        suggested_binds.append(f"/usr/lib (因为缺少库 {lib})")

    # 匹配 docker socket 缺失
    if "docker" in command and "Cannot connect to the Docker daemon" in stderr_text:
        suggested_binds.append("/var/run/docker.sock")
        if not allow_network:
            stderr_text += "\n[提示] Docker命令还需要 allow_network=True"

    # 匹配 nvidia 相关错误
    if ("nvidia" in command or "cuda" in command) and ("libcuda" in stderr_text or "libnvidia" in stderr_text):
        suggested_binds.extend(["/dev/nvidia0", "/dev/nvidiactl", "/dev/nvidia-modeset", "/dev/nvidia-uvm",
                                "/usr/lib/x86_64-linux-gnu/libcuda*"])

    # 匹配外部命令未找到（但 /usr/bin 已挂载，一般不会是此问题）
    if "command not found" in stderr_text:
        missing_cmd = re.search(r"([^:]+): command not found", stderr_text)
        if missing_cmd:
            suggested_binds.append(f"{missing_cmd.group(1)} 所在目录（可能需挂载）")

    # 通用文件未找到（比如访问了宿主机特定路径）
    nofile_match = re.findall(r"No such file or directory: (.+)", stderr_text)
    for p in nofile_match:
        # 只提示真实路径，且避免重复
        if p.startswith("/") and p not in suggested_binds:
            suggested_binds.append(os.path.dirname(p) if not os.path.isdir(p) else p)

    # 去重并限制数量
    suggested_binds = list(dict.fromkeys(suggested_binds))[:5]

    # 构造返回信息
    return_dict = {
        "success": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": stdout_text,
        "stderr": stderr_text,
        "error": "命令执行失败" if result.returncode != 0 else "",
        "details": "执行成功：" + stderr_text if result.returncode != 0 else stdout_text,
    }

    if suggested_binds:
        return_dict["suggested_extra_ro_binds"] = suggested_binds
        return_dict["hint"] = "请用 extra_ro_binds 参数重试，并检查 allow_network 是否需要打开"

    return return_dict

@function_tool
def python3(code: str, allowed_dir: str, allow_network: bool = False,
            extra_ro_binds: Optional[List[str]] = None) -> dict:
    """
    在隔离的沙箱环境中执行 Python 代码。
    Args:
        code: Python代码
        allowed_dir: 允许读写的目录（会被可读写挂载），必须位于 /home/{uname}/ 下
        allow_network: 是否允许网络访问（默认 False）
        extra_ro_binds: 额外只读挂载的文件或目录，用于暴露沙箱外资源。
                       推荐用法：
                       - Docker命令：extra_ro_binds=["/var/run/docker.sock"]，且 allow_network=True
                       - NVIDIA GPU：extra_ro_binds=["/dev/nvidia0", "/dev/nvidiactl", "/dev/nvidia-modeset",
                                           "/dev/nvidia-uvm", "/usr/lib/x86_64-linux-gnu/libcuda*"]
                       - 第三方库（conda等）：extra_ro_binds=["/opt/conda", "/usr/local/lib"]
                       若命令失败，返回结果中会包含 suggested_extra_ro_binds 字段，请按建议重试。
    Returns:
        结构化字典，包含 success, error, details, stdout, stderr, suggested_extra_ro_binds 等字段
    """
    abs_path = os.path.abspath(allowed_dir)
    if not Path(abs_path).is_relative_to(Path(HOME)):
        typer.echo(typer.style(f"[Error]安全限制：只能访问用户主目录下的路径，禁止访问 {abs_path}", fg=typer.colors.RED))
        return {"success": False, "error": "安全限制", "details": f"只能访问当前用户主目录下的路径，禁止访问 {abs_path}"}

    typer.echo(typer.style(f"[执行中]正在隔离的{abs_path}目录下执行Python代码：{code[:20]}，网络访问权限：{'允许' if allow_network else '禁止'}", fg=typer.colors.WHITE))

    executor = BubblewrapExecutor(
        allowed_dir=abs_path,
        allow_network=allow_network,
        extra_ro_binds=extra_ro_binds
    )

    try:
        result = executor.run(code, "python")
    except TimeoutError as e:
        typer.echo(typer.style(f"[Error]运行超时：{str(e)}", fg=typer.colors.RED))
        return {"success": False, "error": "运行超时", "details": str(e)}
    except RuntimeError as e:
        typer.echo(typer.style(f"[Error]运行失败：{str(e)}", fg=typer.colors.RED))
        return {"success": False, "error": "运行失败", "details": str(e)}
    except Exception as e:
        typer.echo(typer.style(f"[Error]发生错误：{str(e)}", fg=typer.colors.RED))
        return {"success": False, "error": "发生错误", "details": str(e)}

    # ---- 分析 stderr，推断缺失的只读绑定 ----
    suggested_binds = []
    stderr_text = result.stderr or ""
    stdout_text = result.stdout or ""

    # 1. 动态库缺失
    match = re.search(r"error while loading shared libraries: (.+?):", stderr_text)
    if match:
        lib = match.group(1)
        suggested_binds.append(f"/usr/lib (缺少库 {lib})")

    # 2. Docker socket 缺失
    if "Cannot connect to the Docker daemon" in stderr_text:
        suggested_binds.append("/var/run/docker.sock")
        if not allow_network:
            stderr_text += "\n[提示] Docker命令还需要 allow_network=True"

    # 3. NVIDIA 相关错误
    if ("libcuda" in stderr_text or "libnvidia" in stderr_text):
        suggested_binds.extend([
            "/dev/nvidia0", "/dev/nvidiactl", "/dev/nvidia-modeset",
            "/dev/nvidia-uvm", "/usr/lib/x86_64-linux-gnu/libcuda.so*"
        ])

    # 4. 命令未找到（Python的 subprocess 错误等）
    if "command not found" in stderr_text:
        missing_cmd = re.search(r"([^\s:]+): command not found", stderr_text)
        if missing_cmd:
            suggested_binds.append(f"{missing_cmd.group(1)} 所在目录（可能需挂载）")

    # 5. 通用文件未找到
    nofile_matches = re.findall(r"No such file or directory: '?([^'\n]+?)'?", stderr_text)
    for p in nofile_matches:
        p = p.strip()
        if p.startswith("/") and p not in suggested_binds:
            suggested_binds.append(os.path.dirname(p))

    # 去重并限制数量
    suggested_binds = list(dict.fromkeys(suggested_binds))[:5]

    # 构造返回
    return_dict = {
        "success": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": stdout_text,
        "stderr": stderr_text,
        "error": "Python代码执行失败" if result.returncode != 0 else "",
        "details": "执行成功:" + stderr_text if result.returncode != 0 else stdout_text,
    }

    if suggested_binds:
        return_dict["suggested_extra_ro_binds"] = suggested_binds
        return_dict["hint"] = "请用 extra_ro_binds 参数重试，并检查 allow_network 是否需要打开"

    return return_dict