from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.core.config import settings


def get_user_timezone(timezone_name: str | None = None) -> ZoneInfo:
    return ZoneInfo(timezone_name or settings.timezone)


def now_in(timezone_name: str | None = None) -> datetime:
    return datetime.now(get_user_timezone(timezone_name))


def to_utc_scheduled(local_scheduled: datetime) -> datetime:
    """Resolve a wall-clock local scheduled time to canonical UTC.

    PEP 495 non-existent wall times (spring-forward gap) are shifted
    forward to the next valid wall-clock. Ambiguous fall-back times use
    Python's default fold=0 (first occurrence).
    """
    utc = local_scheduled.astimezone(UTC)
    back = utc.astimezone(local_scheduled.tzinfo)
    if (
        back.hour != local_scheduled.hour
        or back.minute != local_scheduled.minute
        or back.second != local_scheduled.second
    ):
        return back.astimezone(UTC)
    return utc


__all__ = ["get_user_timezone", "now_in", "to_utc_scheduled"]
