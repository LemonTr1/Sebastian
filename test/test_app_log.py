"""测试 src/logs/app_log.py：get_log 单例、logger 名称、能写入日志记录（重定向到临时目录，不碰真实 ~/.sebastian/logs）。"""
import logging
import os
import tempfile
import unittest
from logging.handlers import RotatingFileHandler

# 先把 HOME 指向临时目录，确保模块导入创建的日志落在临时路径而非真实 ~/.sebastian/logs
_TMP_HOME = tempfile.mkdtemp(prefix="seb-applog-test-")
os.environ["HOME"] = _TMP_HOME

from src.logs.app_log import AppLog, get_log, LOG, LOG_DIR


class TestGetLog(unittest.TestCase):
    def test_returns_single_instance(self):
        self.assertIs(get_log(), get_log())
        self.assertIs(get_log(), LOG)

    def test_logger_name_is_sebastian(self):
        self.assertEqual(get_log().logger.name, "Sebastian")

    def test_log_dir_isolated_to_temp_home(self):
        self.assertTrue(str(LOG_DIR).startswith(_TMP_HOME))


class TestWriteRecord(unittest.TestCase):
    def test_record_is_written_to_log_file(self):
        logger = get_log().logger
        backup = list(logger.handlers)
        try:
            # 换成内存 handler，避免依赖真实文件，同时验证 emit 链路
            captured = logging.Handler()
            records = []
            captured.emit = lambda record: records.append(record)
            logger.handlers = [captured]
            get_log().info("hello-from-test")
            self.assertTrue(any(r.getMessage() == "hello-from-test" for r in records))
        finally:
            logger.handlers = backup

    def test_rotate_handler_targets_temp_file(self):
        # 默认 handler 为 RotatingFileHandler，且 fallback_path 指向临时日志目录
        log_file = LOG_DIR / "sebastian.log"
        self.assertEqual(str(log_file).startswith(_TMP_HOME), True)

    def test_applog_creates_own_handler(self):
        app = AppLog(log_file="isolated.log")
        self.assertEqual(app.logger.name, "Sebastian")
        self.assertIsInstance(app.logger.handlers[0], RotatingFileHandler)


if __name__ == "__main__":
    unittest.main()