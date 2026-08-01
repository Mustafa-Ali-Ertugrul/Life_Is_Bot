import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.timezone import get_user_timezone, now_in
from app.models import BotKey, Habit, ReminderEvent, ReminderStatus, User
from app.services import reminder_service

RELATED_TYPE = "habit"


def parse_days(days_of_week: str) -> set[int]:
    days: set[int] = set()
    for part in days_of_week.split(","):
        part = part.strip()
        if part.isdigit():
            days.add(int(part))
    return days


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
    await session.commit()
    await session.refresh(habit)
    return habit


async def list_habits(session: AsyncSession, user_id: int) -> list[Habit]:
    result = await session.execute(
        select(Habit).where(Habit.user_id == user_id).order_by(Habit.created_at)
    )
    return list(result.scalars().all())


async def get_habit(session: AsyncSession, habit_id: int) -> Habit | None:
    result = await session.execute(select(Habit).where(Habit.id == habit_id))
    return result.scalar_one_or_none()


async def toggle_habit(session: AsyncSession, habit_id: int, is_active: bool) -> Habit | None:
    habit = await get_habit(session, habit_id)
    if habit is None:
        return None
    habit.is_active = is_active
    await session.commit()
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
        scheduled_at = local_scheduled.astimezone(UTC)
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


async def generate_today_events_for_all(session: AsyncSession) -> int:
    result = await session.execute(
        select(Habit)
        .join(User, Habit.user_id == User.id)
        .where(Habit.is_active.is_(True), User.is_active.is_(True))
    )
    habits = list(result.scalars().all())
    user_ids = {habit.user_id for habit in habits}
    created = 0
    for user_id in user_ids:
        events = await generate_today_events(session, user_id)
        created += len(events)
    return created


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
    "generate_today_events_for_all",
    "get_completion_stats",
    "get_habit",
    "list_habits",
    "parse_days",
    "toggle_habit",
]
