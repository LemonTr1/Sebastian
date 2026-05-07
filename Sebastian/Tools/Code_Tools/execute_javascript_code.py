import docker
import tempfile
import os
import json
import shutil
import requests
from docker.errors import ImageNotFound, APIError
from agents import function_tool
import typer

@function_tool
def execute_javascript_code(
        code: str,
        timeout: int = 10,
        memory_limit: str = '128m',
        cpu_limit: float = 1.0
)->str:
    """
    在隔离的JavaScript沙箱中执行用户提供的或未知外来的JavaScript代码，返回输出和状态。
    Args:
        code: 要执行的 JavaScript 代码字符串
        timeout: 最长执行时间（秒）
        memory_limit: 内存限制，如 '128m'
        cpu_limit: CPU 核数限制，如 1.0 表示一个核
    Returns:
        json字符串: {
            "success": bool,
            "output": str,      # 合并 stdout 和 stderr
            "exit_code": int,   # 进程返回码
            "error": str | None # 错误信息
        }
    """
    typer.echo(typer.style(f"[执行中]正在将JavaScript代码：`{code[:20]}`放入沙箱执行...",fg=typer.colors.WHITE))
    result = {
        "success": False,
        "output": "",
        "exit_code": -1,
        "error": None
    }
    #导入docker虚拟环境
    client = docker.from_env()
    #创建临时目录（在系统自带的临时目录下再创建一个子目录，用完即弃）
    temp_dir = tempfile.mkdtemp()
    #在临时目录中创建代码文件路径
    script_path = os.path.join(temp_dir, "script.js")

    container = None
    try:
        # 将代码写入临时文件
        with open(script_path, "w", encoding='utf-8') as file:
            file.write(code)

        # 确保容器内的 nobody 用户可以读取
        os.chmod(temp_dir, 0o711)       # 目录：rwx--x--x
        os.chmod(script_path, 0o644)    # 文件：rw-r--r--

        try:
            #在虚拟环境中执行代码
            container = client.containers.run(
                image="node:20-slim",
                #容器启动后执行命令：node /sandbox/script.js
                command=["node", "/sandbox/script.js"],
                volumes={
                    #将temp_dir挂载到容器里的/sandbox,并只读模式
                    #宿主机中/tmp/{temp_dir}/script.js 相当于 容器中/sandbox/script.js
                    temp_dir: {
                        'bind': '/sandbox',
                        'mode': 'ro'
                    }
                },
                network_disabled=True, #禁用网络
                mem_limit=memory_limit, #内存限制
                cpu_period=100000,
                cpu_quota=int(cpu_limit*100000),
                pids_limit=50, #限制进程数
                read_only=True, #只读
                user="nobody", #非root运行，nobody是一个具体的、几乎没有任何权限的特殊用户
                detach=True, #后台运行
                stdout=True, stderr=True,
            )
        except ImageNotFound as e:
            typer.echo(typer.style(f"[执行中]镜像 node:20-slim 不存在，正在拉取镜像...", fg=typer.colors.WHITE))
            #首次需要拉取镜像
            client.images.pull("node:20-slim")
            #再重新在Docker中运行JavaScript代码
            container = client.containers.run(
                image="node:20-slim",
                command=["node", "/sandbox/script.js"],
                volumes={temp_dir: {'bind': '/sandbox', 'mode': 'ro'}},
                network_disabled=True,
                mem_limit=memory_limit,
                cpu_period=100000,
                cpu_quota=int(cpu_limit * 100000),
                pids_limit=50,
                read_only=True,
                user="nobody",
                detach=True,
                stdout=True, stderr=True,
            )
        except Exception as e:
            result["error"] = f"出现未知错误: {e}"
            return json.dumps(result, ensure_ascii=False)

        #等待容器执行完成，带超时
        try:
            container.wait(timeout=timeout)
        except requests.exceptions.ReadTimeout as e:
            # 超时强制终止
            container.kill()
            result["error"] = f"Execution timed out after {timeout}s: {e}"
            result["output"] = container.logs(stdout=True, stderr=True).decode(
                'utf-8', errors='replace')
            return json.dumps(result, ensure_ascii=False)

        # 获取日志和退出码
        logs = container.logs(stdout=True, stderr=True).decode('utf-8', errors='replace')
        exit_code = container.attrs['State']['ExitCode']
        result["output"] = logs
        result["exit_code"] = exit_code
        result["success"] = (exit_code == 0)
        return json.dumps(result, ensure_ascii=False)
    except APIError as e:
        result["error"] = f"Docker API error: {e}"
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        result["error"] = f"Unexpected error: {e}"
        return json.dumps(result, ensure_ascii=False)
    finally:
        #清理资源
        if container:
            try:
                #强制删除沙箱环境
                container.remove(force=True)
            except Exception:
                pass
        #清理创建的/tmp/{temp_dir}目录和其中文件
        shutil.rmtree(temp_dir, ignore_errors=True)
