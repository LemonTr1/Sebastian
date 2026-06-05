from datetime import datetime, timezone, timedelta
import json


def get_current_time(timezone_offset: int = 8) -> str:
    tz = timezone(timedelta(hours=timezone_offset))
    now = datetime.now(tz)
    return json.dumps({
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "weekday": now.strftime("%A"),
        "iso_format": now.isoformat(),
        "timezone": f"UTC+{timezone_offset}",
        "year": now.year,
        "month": now.month,
        "day": now.day,
        "timestamp": int(now.timestamp()),
    }, ensure_ascii=False)
