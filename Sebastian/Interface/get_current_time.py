import json
from datetime import datetime, timezone, timedelta

def get_current_time(timezone_offset: int = 8) -> str:
    """
    内部函数：获取指定时区偏移的当前时间信息。
    timezone_offset: 时区偏移小时数，例如中国为 +8。
    """
    tz = timezone(timedelta(hours=timezone_offset))
    now = datetime.now(tz)

    return json.dumps({
        "date": now.strftime("%Y-%m-%d"),        # 例如 2026-04-30
        "time": now.strftime("%H:%M:%S"),        # 例如 14:35:22
        "weekday": now.strftime("%A"),           # 例如 Thursday
        "iso_format": now.isoformat(),
        "timezone": f"UTC{timezone_offset:+d}",
        "year": now.year,
        "month": now.month,
        "day": now.day,
        "timestamp": now.timestamp()
    })
