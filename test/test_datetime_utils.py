# 测 get_current_time 返回的 JSON 结构：日期格式、时区、年/月/日字段与偏移分支
import json
import re
import unittest
from unittest.mock import patch

from src.utils.datetime_utils import get_current_time

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class TestGetCurrentTime(unittest.TestCase):
    def test_default_offset_returns_valid_json(self):
        data = json.loads(get_current_time())
        self.assertIn("date", data)
        self.assertIn("timezone", data)
        self.assertIn("year", data)
        self.assertIn("month", data)
        self.assertIn("day", data)
        self.assertRegex(data["date"], DATE_RE)

    def test_default_timezone_is_utc8(self):
        data = json.loads(get_current_time())
        self.assertEqual(data["timezone"], "UTC+8")

    def test_zero_offset(self):
        data = json.loads(get_current_time(timezone_offset=0))
        self.assertEqual(data["timezone"], "UTC+0")

    def test_negative_offset(self):
        # 实现按字面拼接，负偏移表现为 "UTC+-5"
        data = json.loads(get_current_time(timezone_offset=-5))
        self.assertEqual(data["timezone"], "UTC+-5")

    def test_year_month_day_match_date(self):
        data = json.loads(get_current_time())
        y, m, d = data["date"].split("-")
        self.assertEqual(data["year"], int(y))
        self.assertEqual(data["month"], int(m))
        self.assertEqual(data["day"], int(d))

    def test_utc8_date_equals_computed_expected(self):
        # 用同一 tz 推导期望值，验证日期一致（依赖真实当前时刻，但结果确定）
        from datetime import datetime, timedelta, timezone

        tz = timezone(timedelta(hours=8))
        now = datetime.now(tz)
        data = json.loads(get_current_time())
        self.assertEqual(data["date"], now.strftime("%Y-%m-%d"))


if __name__ == "__main__":
    unittest.main()