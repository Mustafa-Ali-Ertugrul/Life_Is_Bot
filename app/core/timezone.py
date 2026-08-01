from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import settings


def get_user_timezone(timezone_name: str | None = None) -> ZoneInfo:
    return ZoneInfo(timezone_name or settings.timezone)


def now_in(timezone_name: str | None = None) -> datetime:
    return datetime.now(get_user_timezone(timezone_name))
