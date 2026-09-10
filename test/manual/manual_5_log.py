from src.logs.app_log import get_log

if __name__ == "__main__":
    log = get_log()
    log.info("这是一个测试日志信息。")
    log.error("这是一个测试错误日志信息。")