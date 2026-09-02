import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import InvalidStateError, NotFoundError
from app.core.schedule import parse_days
from app.core.timezone import get_user_timezone, now_in, to_utc_scheduled
from app.models import BotKey, Habit, ReminderEvent, ReminderStatus, User
from app.services import preference_service, reminder_service

RELATED_TYPE = "habit"


async def create_habit(
    session: AsyncSession,
    user_id: int,
    name: str,
    target_hour: int,
    target_minute: int,
    days_of_week: str,
) -> Habit:
    habit = Habit(
        user_id=user_id,
        name=name,
        target_hour=target_hour,
        target_minute=target_minute,
        days_of_week=days_of_week,
        is_active=True,
    )
    session.add(habit)
    await session.flush()
    await session.refresh(habit)
    await preference_service.toggle_preference(session, user_id, BotKey.HABIT, enabled=True)
    return habit


async def list_habits(
    session: AsyncSession, user_id: int, *, active_only: bool = False
) -> list[Habit]:
    stmt = select(Habit).where(Habit.user_id == user_id)
    if active_only:
        stmt = stmt.where(Habit.is_active.is_(True))
    stmt = stmt.order_by(Habit.created_at)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_habit(session: AsyncSession, habit_id: int) -> Habit | None:
    result = await session.execute(select(Habit).where(Habit.id == habit_id))
    return result.scalar_one_or_none()


async def toggle_habit(session: AsyncSession, habit_id: int, is_active: bool) -> Habit | None:
    habit = await get_habit(session, habit_id)
    if habit is None:
        return None
    habit.is_active = is_active
    await session.flush()
    await session.refresh(habit)
    return habit


async def update_habit(
    session: AsyncSession,
    habit_id: int,
    *,
    name: str | None = None,
    target_hour: int | None = None,
    target_minute: int | None = None,
    days_of_week: str | None = None,
    is_active: bool | None = None,
) -> Habit:
    """Partially update a habit."""
    habit = await get_habit(session, habit_id)
    if habit is None:
        raise NotFoundError(f"Habit {habit_id} not found")

    if name is not None:
        if not name.strip():
            raise InvalidStateError("name must not be empty")
        habit.name = name.strip()
    if target_hour is not None:
        if not 0 <= target_hour <= 23:
            raise InvalidStateError("target_hour must be between 0 and 23")
        habit.target_hour = target_hour
    if target_minute is not None:
        if not 0 <= target_minute <= 59:
            raise InvalidStateError("target_minute must be between 0 and 59")
        habit.target_minute = target_minute
    if days_of_week is not None:
        habit.days_of_week = days_of_week
    if is_active is not None:
        habit.is_active = is_active

    await session.flush()
    await session.refresh(habit)
    return habit


async def generate_today_events(
    session: AsyncSession, user_id: int, now: datetime | None = None
) -> list[ReminderEvent]:
    tz = get_user_timezone(await _user_timezone_name(session, user_id))
    base = now if now is not None else now_in()
    if base.tzinfo is None:
        base = base.replace(tzinfo=UTC)
    local_now = base.astimezone(tz)
    weekday = local_now.isoweekday()
    habits = await list_habits(session, user_id)
    events: list[ReminderEvent] = []
    for habit in habits:
        if not habit.is_active:
            continue
        if weekday not in parse_days(habit.days_of_week):
            continue
        local_scheduled = local_now.replace(
            hour=habit.target_hour,
            minute=habit.target_minute,
            second=0,
            microsecond=0,
        )
        scheduled_at = to_utc_scheduled(local_scheduled)
        event = await reminder_service.create_event(
            session,
            user_id=user_id,
            bot_key=BotKey.HABIT,
            scheduled_at=scheduled_at,
            related_type=RELATED_TYPE,
            related_id=habit.id,
            interpretation_json=json.dumps({"habit_name": habit.name}, ensure_ascii=False),
        )
        events.append(event)
    return events


async def _user_timezone_name(session: AsyncSession, user_id: int) -> str:
    result = await session.execute(select(User.timezone).where(User.id == user_id))
    return result.scalar_one_or_none() or settings.timezone


async def get_completion_stats(
    session: AsyncSession, user_id: int, days: int = 7, now: datetime | None = None
) -> dict[str, int]:
    since = (now if now is not None else now_in("UTC")) - timedelta(days=days)
    result = await session.execute(
        select(ReminderEvent).where(
            ReminderEvent.user_id == user_id,
            ReminderEvent.related_type == RELATED_TYPE,
            ReminderEvent.scheduled_at >= since,
        )
    )
    events = list(result.scalars().all())
    total = len(events)
    completed = sum(1 for e in events if e.status == ReminderStatus.POSITIVE.value)
    return {"total": total, "completed": completed}


__all__ = [
    "Habit",
    "RELATED_TYPE",
    "create_habit",
    "generate_today_events",
    "get_completion_stats",
    "get_habit",
    "list_habits",
    "parse_days",
    "toggle_habit",
    "update_habit",
]
