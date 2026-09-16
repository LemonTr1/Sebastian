from datetime import datetime, timezone, timedelta
import json


def get_current_time(timezone_offset: int = 8) -> str:
    tz = timezone(timedelta(hours=timezone_offset))
    now = datetime.now(tz)
    return json.dumps({
        "date": now.strftime("%Y-%m-%d"),
        "timezone": f"UTC+{timezone_offset}",
        "year": now.year,
        "month": now.month,
        "day": now.day,
    }, ensure_ascii=False)
