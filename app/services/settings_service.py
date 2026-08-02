from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidStateError, NotFoundError
from app.core.quiet_hours import is_valid_hhmm
from app.models import User


def is_valid_timezone(name: str) -> bool:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


async def get_settings(session: AsyncSession, user_id: int) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFoundError(f"Kullanıcı bulunamadı: {user_id}")
    return user


async def update_timezone(session: AsyncSession, user_id: int, timezone_name: str) -> User:
    if not is_valid_timezone(timezone_name):
        raise InvalidStateError("Geçersiz timezone. IANA adı kullan (örn: Europe/Istanbul).")
    user = await get_settings(session, user_id)
    user.timezone = timezone_name
    await session.flush()
    return user


async def toggle_notifications(session: AsyncSession, user_id: int) -> bool:
    user = await get_settings(session, user_id)
    user.notifications_enabled = not user.notifications_enabled
    await session.flush()
    return user.notifications_enabled


async def set_quiet_hours(session: AsyncSession, user_id: int, start: str, end: str) -> User:
    if not is_valid_hhmm(start) or not is_valid_hhmm(end):
        raise InvalidStateError("Saat formatı geçersiz. HH:MM şeklinde yaz (örn: 23:00).")
    user = await get_settings(session, user_id)
    user.quiet_hours_start = start
    user.quiet_hours_end = end
    user.quiet_hours_enabled = True
    await session.flush()
    return user


async def clear_quiet_hours(session: AsyncSession, user_id: int) -> User:
    user = await get_settings(session, user_id)
    user.quiet_hours_start = None
    user.quiet_hours_end = None
    user.quiet_hours_enabled = False
    await session.flush()
    return user


__all__ = [
    "clear_quiet_hours",
    "get_settings",
    "is_valid_hhmm",
    "is_valid_timezone",
    "set_quiet_hours",
    "toggle_notifications",
    "update_timezone",
]
