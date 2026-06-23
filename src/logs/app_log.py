import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

CURRENT_DIR = Path(__file__).parent.resolve()

class AppLog:
    def __init__(
        self,
        log_file: str = "sebastian.log",
        level = logging.INFO,
        max_bytes: int = 5 * 1024 * 1024, #单个文件最大5MB
        backup_count: int = 5 #保留5个备份
    ):
        self.logger = logging.getLogger("Sebastian")
        self.logger.setLevel(level)
        self.logger.handlers = []

        log_path = CURRENT_DIR / log_file

        # 按大小轮转
        handler = RotatingFileHandler(
            log_path,
            maxBytes=max_bytes, #达到此大小自动分割
            backupCount=backup_count, #保留几个备份文件
            encoding='utf-8'
        )

        handler.setLevel(level)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%d-%b-%y %H:%M:%S'
        ))

        self.logger.addHandler(handler)
        self.log_path = log_path

    def debug(self, message: str):   self.logger.debug(message)
    def info(self, message: str):    self.logger.info(message)
    def warning(self, message: str): self.logger.warning(message)
    def error(self, message: str):   self.logger.error(message)


LOG = AppLog()

def get_log():
    return LOG

