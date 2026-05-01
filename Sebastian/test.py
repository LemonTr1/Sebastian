import subprocess

cmd = "sudo apt update"
try:
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
    print("stdout:", result.stdout)
    print("stderr:", result.stderr)
    print("returncode:", result.returncode)
except subprocess.TimeoutExpired:
    print("超时")
except Exception as e:
    print("异常:", type(e), e)
