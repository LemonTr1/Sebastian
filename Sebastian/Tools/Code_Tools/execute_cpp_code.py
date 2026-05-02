import os
import json
import shutil
import tempfile
import docker
from docker.errors import ImageNotFound, APIError
from agents import function_tool
import typer


@function_tool
def execute_cpp_code(
        code: str,
        language: str,  # "c" or "cpp"
        timeout: int = 10,
        memory_limit: str = '128m',
        cpu_limit: float = 1.0,
        stdin_data: str = ""  # 新增：支持标准输入
) -> str:
    """
    在安全的Docker容器中编译并执行不可信的C/C++代码。
    """
    typer.echo(typer.style(f"[执行中]正在将代码放入C/C++沙箱中编译执行...", fg=typer.colors.WHITE))

    # 1. 参数校验
    if language not in ("c", "cpp"):
        return json.dumps({"success": False, "output": "", "exit_code": -1, "error": f"不支持的语言类型: {language}"},
                          ensure_ascii=False)

    # 2. 构建编译命令
    if language == "c":
        compiler = "gcc"
        filename = "script.c"
    else:
        compiler = "g++"
        filename = "script.cpp"

    client = docker.from_env()
    temp_dir = tempfile.mkdtemp()
    script_path = os.path.join(temp_dir, filename)
    container = None

    try:
        # 写入源代码，使用默认更安全的权限
        with open(script_path, "w", encoding='utf-8') as f:
            f.write(code)
        os.chmod(script_path, 0o644)

        # 这是需要传递给容器入口（Entrypoint）的参数，而不是覆盖"command"
        build_command = f"{compiler} -o /tmp/a.out /sandbox/{filename} && /tmp/a.out"

        container_kwargs = {
            "image": "gcc:alpine",  # 优化：使用更轻量的Alpine版本
            "command": ["sh", "-c", build_command],  # 通过command传递参数
            "volumes": {temp_dir: {'bind': '/sandbox', 'mode': 'ro'}},
            "tmpfs": {"/tmp": "size=64m,mode=1777"},
            "network_disabled": True,
            "mem_limit": memory_limit,
            "memswap_limit": memory_limit,  # 限制swap，防止耗尽宿主机内存
            "cpu_period": 100000,
            "cpu_quota": int(cpu_limit * 100000),
            "pids_limit": 50,
            "read_only": True,
            "user": "nobody",
            "detach": True,
            "stdin": True,  # 开启标准输入
            "stdin_open": True,  # 保持标准输入打开
        }

        # 处理标准输入
        if stdin_data:
            container_kwargs["stdin_open"] = True

        try:
            container = client.containers.run(**container_kwargs)
        except ImageNotFound:
            client.images.pull("gcc:alpine")
            container = client.containers.run(**container_kwargs)
        except Exception as e:
            return json.dumps({"success": False, "output": "", "exit_code": -1, "error": f"启动容器失败: {e}"},
                              ensure_ascii=False)

        # 写入标准输入
        if stdin_data and container:
            container.exec_run("cat > /tmp/stdin_input", input=stdin_data.encode())

        try:
            container.wait(timeout=timeout)
            exit_code = container.attrs['State']['ExitCode']
            logs = container.logs(stdout=True, stderr=True).decode('utf-8', errors='replace')
            return json.dumps({
                "success": exit_code == 0,
                "output": logs,
                "exit_code": exit_code,
                "error": None
            }, ensure_ascii=False)
        except Exception as e:
            container.kill()
            return json.dumps({
                "success": False,
                "output": container.logs(stdout=True, stderr=True).decode('utf-8', errors='replace'),
                "exit_code": -1,
                "error": f"执行超时 ({timeout}s) 或发生错误"
            }, ensure_ascii=False)

    except APIError as e:
        return json.dumps({"success": False, "output": "", "exit_code": -1, "error": f"Docker API 错误: {e}"},
                          ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "output": "", "exit_code": -1, "error": f"未知错误: {e}"},
                          ensure_ascii=False)
    finally:
        if container:
            try:
                container.remove(force=True)
            except Exception:
                pass
        shutil.rmtree(temp_dir, ignore_errors=True)
