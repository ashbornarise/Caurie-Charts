from datetime import datetime, timedelta, timezone


def now_utc(delta_seconds: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=delta_seconds)).strftime("%Y-%m-%d %H:%M:%S")
