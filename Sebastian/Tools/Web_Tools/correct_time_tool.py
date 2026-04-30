from agents import function_tool
import json
from datetime import datetime, timezone, timedelta

def get_current_time(timezone_offset: int = 8) -> dict:
    """
    内部函数：获取指定时区偏移的当前时间信息。
    timezone_offset: 时区偏移小时数，例如中国为 +8。
    """
    tz = timezone(timedelta(hours=timezone_offset))
    now = datetime.now(tz)

    return {
        "date": now.strftime("%Y-%m-%d"),        # 例如 2026-04-30
        "time": now.strftime("%H:%M:%S"),        # 例如 14:35:22
        "weekday": now.strftime("%A"),           # 例如 Thursday
        "iso_format": now.isoformat(),
        "timezone": f"UTC{timezone_offset:+d}",
        "year": now.year,
        "month": now.month,
        "day": now.day,
        "timestamp": now.timestamp()
    }

@function_tool
def get_current_datetime(timezone_offset: int = 8) -> str:
    """
    获取当前日期和时间。
    当用户询问今天的日期、当前时间、星期几、或者需要基于实时时间进行计算或时效性信息查询时，都应该调用此工具。
    Args:
        timezone_offset: 时区偏移（小时），默认8（东八区/北京时间）。如需其他时区，可传入对应偏移值。
    Returns:
        JSON字符串，包含 date, time, weekday, year, month, day 等字段。
        例如：
        {
            "date": "2026-04-30",
            "time": "14:35:22",
            "weekday": "Thursday",
            "year": 2026,
            ...
        }
    """
    try:
        data = get_current_time(timezone_offset)
        return json.dumps(data, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"时间获取失败: {str(e)}"})
