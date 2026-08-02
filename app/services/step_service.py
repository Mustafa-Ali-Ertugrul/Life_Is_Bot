import json
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.schedule import format_days, parse_days
from app.core.timezone import get_user_timezone, now_in, to_utc_scheduled
from app.models import BotKey, ReminderEvent, StepLog, StepSettings, User
from app.services import preference_service, reminder_service

RELATED_TYPE = "step_goal"

DEFAULT_DAILY_TARGET = 8000
DEFAULT_REMINDER_HOUR = 21
DEFAULT_REMINDER_MINUTE = 0
DEFAULT_DAYS_OF_WEEK = "1,2,3,4,5,6,7"


async def get_settings(session: AsyncSession, user_id: int) -> StepSettings | None:
    result = await session.execute(select(StepSettings).where(StepSettings.user_id == user_id))
    return result.scalar_one_or_none()


async def get_or_create_settings(session: AsyncSession, user_id: int) -> StepSettings:
    settings = await get_settings(session, user_id)
    if settings is not None:
        return settings
    settings = StepSettings(
        user_id=user_id,
        daily_target=DEFAULT_DAILY_TARGET,
        reminder_hour=DEFAULT_REMINDER_HOUR,
        reminder_minute=DEFAULT_REMINDER_MINUTE,
        days_of_week=DEFAULT_DAYS_OF_WEEK,
        is_active=True,
    )
    session.add(settings)
    await session.commit()
    await session.refresh(settings)
    await preference_service.toggle_preference(session, user_id, BotKey.STEP, enabled=True)
    return settings


async def update_daily_target(
    session: AsyncSession, user_id: int, daily_target: int
) -> StepSettings:
    if not 0 <= daily_target <= 100000:
        raise ValueError("daily_target must be between 0 and 100000")
    settings = await get_or_create_settings(session, user_id)
    settings.daily_target = daily_target
    await session.commit()
    await session.refresh(settings)
    return settings


async def update_reminder_time(
    session: AsyncSession, user_id: int, reminder_hour: int, reminder_minute: int
) -> StepSettings:
    if not 0 <= reminder_hour <= 23:
        raise ValueError("reminder_hour must be between 0 and 23")
    if not 0 <= reminder_minute <= 59:
        raise ValueError("reminder_minute must be between 0 and 59")
    settings = await get_or_create_settings(session, user_id)
    settings.reminder_hour = reminder_hour
    settings.reminder_minute = reminder_minute
    await session.commit()
    await session.refresh(settings)
    return settings


async def toggle_step_bot(session: AsyncSession, user_id: int, is_active: bool) -> StepSettings:
    settings = await get_or_create_settings(session, user_id)
    settings.is_active = is_active
    await session.commit()
    await session.refresh(settings)
    return settings


async def update_days_of_week(session: AsyncSession, user_id: int, days: list[int]) -> StepSettings:
    settings = await get_or_create_settings(session, user_id)
    settings.days_of_week = format_days(days)
    await session.commit()
    await session.refresh(settings)
    return settings


async def get_steps_for_date(session: AsyncSession, user_id: int, log_date: date) -> StepLog | None:
    result = await session.execute(
        select(StepLog).where(
            StepLog.user_id == user_id,
            StepLog.log_date == log_date,
        )
    )
    return result.scalar_one_or_none()


async def get_today_steps(session: AsyncSession, user_id: int) -> StepLog | None:
    tz = get_user_timezone(await _user_timezone_name(session, user_id))
    local_date = now_in("UTC").astimezone(tz).date()
    return await get_steps_for_date(session, user_id, local_date)


async def log_steps(
    session: AsyncSession,
    user_id: int,
    steps: int,
    log_date: date,
    source: str = "manual",
) -> StepLog:
    if not 0 <= steps <= 200000:
        raise ValueError("steps must be between 0 and 200000")
    existing = await get_steps_for_date(session, user_id, log_date)
    if existing is not None:
        existing.steps = steps
        existing.source = source
        await session.commit()
        await session.refresh(existing)
        return existing
    log = StepLog(user_id=user_id, log_date=log_date, steps=steps, source=source)
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log


async def _user_timezone_name(session: AsyncSession, user_id: int) -> str:
    result = await session.execute(select(User.timezone).where(User.id == user_id))
    return result.scalar_one_or_none() or settings.timezone


async def generate_today_events(
    session: AsyncSession, user_id: int, now: datetime | None = None
) -> list[ReminderEvent]:
    tz = get_user_timezone(await _user_timezone_name(session, user_id))
    base = now if now is not None else now_in()
    if base.tzinfo is None:
        base = base.replace(tzinfo=UTC)
    local_now = base.astimezone(tz)
    weekday = local_now.isoweekday()
    step_settings = await get_settings(session, user_id)
    if step_settings is None or not step_settings.is_active:
        return []
    if weekday not in parse_days(step_settings.days_of_week):
        return []
    local_scheduled = local_now.replace(
        hour=step_settings.reminder_hour,
        minute=step_settings.reminder_minute,
        second=0,
        microsecond=0,
    )
    scheduled_at = to_utc_scheduled(local_scheduled)
    event = await reminder_service.create_event(
        session,
        user_id=user_id,
        bot_key=BotKey.STEP,
        scheduled_at=scheduled_at,
        related_type=RELATED_TYPE,
        related_id=step_settings.id,
        interpretation_json=json.dumps(
            {
                "daily_target": step_settings.daily_target,
                "reminder_hour": step_settings.reminder_hour,
                "reminder_minute": step_settings.reminder_minute,
            },
            ensure_ascii=False,
        ),
    )
    return [event]


__all__ = [
    "DEFAULT_DAILY_TARGET",
    "DEFAULT_DAYS_OF_WEEK",
    "DEFAULT_REMINDER_HOUR",
    "DEFAULT_REMINDER_MINUTE",
    "RELATED_TYPE",
    "StepLog",
    "StepSettings",
    "generate_today_events",
    "get_or_create_settings",
    "get_settings",
    "get_steps_for_date",
    "get_today_steps",
    "log_steps",
    "toggle_step_bot",
    "update_daily_target",
    "update_days_of_week",
    "update_reminder_time",
]
