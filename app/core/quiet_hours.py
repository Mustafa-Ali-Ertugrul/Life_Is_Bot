import re
from datetime import datetime, timedelta

TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def is_valid_hhmm(value: str) -> bool:
    return TIME_RE.fullmatch(value) is not None


def parse_hhmm(value: str) -> tuple[int, int] | None:
    match = TIME_RE.fullmatch(value)
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2))


def is_within_quiet_hours(now_local: datetime, start: str, end: str) -> bool:
    start_parts = parse_hhmm(start)
    end_parts = parse_hhmm(end)
    if start_parts is None or end_parts is None:
        return False
    start_minutes = start_parts[0] * 60 + start_parts[1]
    end_minutes = end_parts[0] * 60 + end_parts[1]
    if start_minutes == end_minutes:
        return False
    now_minutes = now_local.hour * 60 + now_local.minute
    if start_minutes < end_minutes:
        return start_minutes <= now_minutes < end_minutes
    return now_minutes >= start_minutes or now_minutes < end_minutes


def next_quiet_end(now_local: datetime, start: str, end: str) -> datetime:
    end_parts = parse_hhmm(end)
    if end_parts is None:
        raise ValueError(f"Geçersiz quiet hours bitişi: {end}")
    candidate = now_local.replace(hour=end_parts[0], minute=end_parts[1], second=0, microsecond=0)
    if candidate <= now_local:
        candidate += timedelta(days=1)
    return candidate


__all__ = [
    "TIME_RE",
    "is_valid_hhmm",
    "is_within_quiet_hours",
    "next_quiet_end",
    "parse_hhmm",
]
