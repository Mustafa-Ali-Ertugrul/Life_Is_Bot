from datetime import UTC, date, datetime, timedelta
from typing import TypedDict
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.timezone import get_user_timezone, now_in
from app.models import ReminderEvent, ReminderStatus, User
from app.services.event_labels import event_label


class DailyReport(TypedDict):
    date: str
    total: int
    completed: int
    missed: int
    unanswered: int
    completed_items: list[str]
    missed_items: list[str]


class WeeklyReport(TypedDict):
    week_start: str
    week_end: str
    total: int
    completed: int
    missed: int
    unanswered: int
    compliance_rate: int
    best_day: int | None
    weakest_day: int | None


async def generate_daily_report(
    session: AsyncSession,
    user_id: int,
    day: date | None = None,
) -> DailyReport:
    tz = get_user_timezone(await _user_timezone_name(session, user_id))
    day = day or _as_local(now_in(), tz).date()

    completed: list[str] = []
    missed: list[str] = []
    unanswered = 0
    for event in await _events_for_local_date(session, user_id, day):
        status = event.status
        if status == ReminderStatus.POSITIVE.value:
            completed.append(event_label(event))
        elif status == ReminderStatus.NEGATIVE.value:
            missed.append(event_label(event))
        else:
            unanswered += 1

    return DailyReport(
        date=day.isoformat(),
        total=len(completed) + len(missed) + unanswered,
        completed=len(completed),
        missed=len(missed),
        unanswered=unanswered,
        completed_items=completed,
        missed_items=missed,
    )


async def generate_weekly_report(
    session: AsyncSession,
    user_id: int,
    week_start: date | None = None,
) -> WeeklyReport:
    tz = get_user_timezone(await _user_timezone_name(session, user_id))
    today = _as_local(now_in(), tz).date()
    week_start = week_start or (today - timedelta(days=today.weekday()))
    week_end = week_start + timedelta(days=7)

    per_day: dict[int, list[int]] = {}
    completed = 0
    missed = 0
    unanswered = 0
    for event in await _events_for_local_date_range(session, user_id, week_start, week_end):
        status = event.status
        weekday = event.scheduled_local_date.isoweekday()
        counts = per_day.setdefault(weekday, [0, 0])
        counts[0] += 1
        if status == ReminderStatus.POSITIVE.value:
            completed += 1
            counts[1] += 1
        elif status == ReminderStatus.NEGATIVE.value:
            missed += 1
        else:
            unanswered += 1

    total = completed + missed + unanswered
    compliance_rate = round(completed / total * 100) if total else 0
    best_day = _best_day(per_day)
    weakest_day = _weakest_day(per_day)

    return WeeklyReport(
        week_start=week_start.isoformat(),
        week_end=(week_end - timedelta(days=1)).isoformat(),
        total=total,
        completed=completed,
        missed=missed,
        unanswered=unanswered,
        compliance_rate=compliance_rate,
        best_day=best_day,
        weakest_day=weakest_day,
    )


async def _user_timezone_name(session: AsyncSession, user_id: int) -> str:
    result = await session.execute(select(User.timezone).where(User.id == user_id))
    name = result.scalar_one_or_none()
    return name or settings.timezone


async def _events_for_local_date(
    session: AsyncSession, user_id: int, day: date
) -> list[ReminderEvent]:
    result = await session.execute(
        select(ReminderEvent).where(
            ReminderEvent.user_id == user_id,
            ReminderEvent.scheduled_local_date == day,
            ReminderEvent.status.notin_(
                [ReminderStatus.CANCELLED.value, ReminderStatus.SUPPRESSED.value]
            ),
        )
    )
    return list(result.scalars().all())


async def _events_for_local_date_range(
    session: AsyncSession,
    user_id: int,
    start: date,
    end: date,
) -> list[ReminderEvent]:
    result = await session.execute(
        select(ReminderEvent).where(
            ReminderEvent.user_id == user_id,
            ReminderEvent.scheduled_local_date >= start,
            ReminderEvent.scheduled_local_date < end,
            ReminderEvent.status.notin_(
                [ReminderStatus.CANCELLED.value, ReminderStatus.SUPPRESSED.value]
            ),
        )
    )
    return list(result.scalars().all())


def _as_local(value: datetime, tz: ZoneInfo) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(tz)


def _best_day(per_day: dict[int, list[int]]) -> int | None:
    if not per_day:
        return None
    return max(
        per_day,
        key=lambda weekday: (per_day[weekday][1] / per_day[weekday][0], per_day[weekday][0]),
    )


def _weakest_day(per_day: dict[int, list[int]]) -> int | None:
    if not per_day:
        return None
    return min(
        per_day,
        key=lambda weekday: (per_day[weekday][1] / per_day[weekday][0], -per_day[weekday][0]),
    )


__all__ = [
    "DailyReport",
    "WeeklyReport",
    "generate_daily_report",
    "generate_weekly_report",
]
