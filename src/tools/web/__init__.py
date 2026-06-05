import os
import json
from datetime import datetime


def get_current_time_str() -> str:
    from datetime import timezone, timedelta
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)
    return json.dumps({
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "weekday": now.strftime("%A"),
        "iso_format": now.isoformat(),
        "timezone": "UTC+8",
        "year": now.year,
        "month": now.month,
        "day": now.day,
        "timestamp": int(now.timestamp()),
    }, ensure_ascii=False)
