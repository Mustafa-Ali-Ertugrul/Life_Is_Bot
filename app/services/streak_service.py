"""Streak (consecutive day) calculation for completion reports."""

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.timezone import now_in
from app.models import ReminderEvent, ReminderStatus, User

LOOKBACK_DAYS = 365


@dataclass(frozen=True)
class StreakReport:
    user_id: int
    current: int
    longest: int
    today_completed: bool


def calculate_streak(completed_days: set[date], today: date) -> int:
    """Count consecutive completed days ending today (or yesterday when pending)."""
    cursor = today if today in completed_days else today - timedelta(days=1)
    streak = 0
    while cursor in completed_days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def calculate_longest_streak(completed_days: set[date]) -> int:
    """Count the longest run of consecutive completed days."""
    longest = 0
    run = 0
    previous: date | None = None
    for day in sorted(completed_days):
        if previous is not None and (day - previous).days == 1:
            run += 1
        else:
            run = 1
        previous = day
        longest = max(longest, run)
    return longest


async def generate_streak_report(session: AsyncSession, user_id: int) -> StreakReport:
    """Build a streak report from completed reminder events in the lookback window.

    A day counts as completed only when every non-cancelled event that day is
    positive. Days with no events break the streak.
    """
    today = await _user_local_today(session, user_id)
    lookback_start = today - timedelta(days=LOOKBACK_DAYS - 1)
    events = await _events_for_lookback(session, user_id, lookback_start, today)

    completed: set[date] = set()
    incomplete: set[date] = set()
    for event in events:
        if event.status == ReminderStatus.POSITIVE.value:
            completed.add(event.scheduled_local_date)
        else:
            incomplete.add(event.scheduled_local_date)
    completed.difference_update(incomplete)

    return StreakReport(
        user_id=user_id,
        current=calculate_streak(completed, today),
        longest=calculate_longest_streak(completed),
        today_completed=today in completed,
    )


async def _user_local_today(session: AsyncSession, user_id: int) -> date:
    result = await session.execute(select(User.timezone).where(User.id == user_id))
    name = result.scalar_one_or_none()
    return now_in(name or settings.timezone).date()


async def _events_for_lookback(
    session: AsyncSession,
    user_id: int,
    start: date,
    end: date,
) -> list[ReminderEvent]:
    result = await session.execute(
        select(ReminderEvent).where(
            ReminderEvent.user_id == user_id,
            ReminderEvent.scheduled_local_date >= start,
            ReminderEvent.scheduled_local_date <= end,
            ReminderEvent.status.notin_(
                [ReminderStatus.CANCELLED.value, ReminderStatus.SUPPRESSED.value]
            ),
        )
    )
    return list(result.scalars().all())


__all__ = [
    "LOOKBACK_DAYS",
    "StreakReport",
    "calculate_longest_streak",
    "calculate_streak",
    "generate_streak_report",
]
