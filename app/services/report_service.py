from calendar import monthrange
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import TypedDict
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.timezone import get_user_timezone, now_in
from app.models import ReminderEvent, ReminderStatus, User
from app.services import step_service
from app.services.event_labels import event_label


class DailyReport(TypedDict):
    date: str
    total: int
    completed: int
    missed: int
    unanswered: int
    completed_items: list[str]
    missed_items: list[str]
    step_steps: int | None
    step_goal: int | None


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


@dataclass(frozen=True)
class BotMonthlyStats:
    bot_key: str
    total: int
    completed: int
    missed: int
    snoozed: int
    pending: int

    @property
    def completion_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return round(self.completed * 100 / self.total, 1)


@dataclass(frozen=True)
class MonthlyReport:
    user_id: int
    year: int
    month: int
    bot_stats: list[BotMonthlyStats] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(s.total for s in self.bot_stats)

    @property
    def total_completed(self) -> int:
        return sum(s.completed for s in self.bot_stats)

    @property
    def total_missed(self) -> int:
        return sum(s.missed for s in self.bot_stats)

    @property
    def total_snoozed(self) -> int:
        return sum(s.snoozed for s in self.bot_stats)

    @property
    def total_pending(self) -> int:
        return sum(s.pending for s in self.bot_stats)

    @property
    def completion_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return round(self.total_completed * 100 / self.total, 1)


@dataclass(frozen=True)
class MonthDaysReport:
    """Per-day schedule/completion flags for a single bot within a month."""

    user_id: int
    year: int
    month: int
    bot_key: str | None
    scheduled_days: list[date] = field(default_factory=list)
    completed_days: list[date] = field(default_factory=list)


@dataclass(frozen=True)
class MonthlyBreakdown:
    """Single month's statistics within a yearly report."""

    month: int
    total: int
    completed: int
    missed: int
    snoozed: int
    pending: int
    completion_rate: float


@dataclass(frozen=True)
class YearlyReport:
    """Yearly completion report for a user aggregated from monthly reports."""

    user_id: int
    year: int
    monthly: list[MonthlyBreakdown] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(m.total for m in self.monthly)

    @property
    def total_completed(self) -> int:
        return sum(m.completed for m in self.monthly)

    @property
    def total_missed(self) -> int:
        return sum(m.missed for m in self.monthly)

    @property
    def total_snoozed(self) -> int:
        return sum(m.snoozed for m in self.monthly)

    @property
    def total_pending(self) -> int:
        return sum(m.pending for m in self.monthly)

    @property
    def completion_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return round(self.total_completed * 100 / self.total, 1)

    @property
    def best_month(self) -> MonthlyBreakdown | None:
        active = [m for m in self.monthly if m.total > 0]
        if not active:
            return None
        return max(active, key=lambda m: m.completion_rate)

    @property
    def worst_month(self) -> MonthlyBreakdown | None:
        active = [m for m in self.monthly if m.total > 0]
        if not active:
            return None
        return min(active, key=lambda m: m.completion_rate)


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

    step_steps: int | None = None
    step_goal: int | None = None
    step_settings = await step_service.get_settings(session, user_id)
    if step_settings is not None:
        step_log = await step_service.get_steps_for_date(session, user_id, day)
        if step_log is not None:
            step_steps = step_log.steps
            step_goal = step_settings.daily_target

    return DailyReport(
        date=day.isoformat(),
        total=len(completed) + len(missed) + unanswered,
        completed=len(completed),
        missed=len(missed),
        unanswered=unanswered,
        completed_items=completed,
        missed_items=missed,
        step_steps=step_steps,
        step_goal=step_goal,
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


async def generate_monthly_report(
    session: AsyncSession,
    user_id: int,
    year: int,
    month: int,
) -> MonthlyReport:
    _, last_day = monthrange(year, month)
    month_start = date(year, month, 1)
    month_end = date(year, month, last_day) + timedelta(days=1)

    per_bot: dict[str, dict[str, int]] = {}
    for event in await _events_for_local_date_range(session, user_id, month_start, month_end):
        counts = per_bot.setdefault(
            event.bot_key,
            {"total": 0, "completed": 0, "missed": 0, "snoozed": 0, "pending": 0},
        )
        counts["total"] += 1
        status = event.status
        if status == ReminderStatus.POSITIVE.value:
            counts["completed"] += 1
        elif status == ReminderStatus.NEGATIVE.value:
            counts["missed"] += 1
        elif status == ReminderStatus.SNOOZED.value:
            counts["snoozed"] += 1
        else:
            counts["pending"] += 1

    bot_stats = [
        BotMonthlyStats(
            bot_key=bot_key,
            total=counts["total"],
            completed=counts["completed"],
            missed=counts["missed"],
            snoozed=counts["snoozed"],
            pending=counts["pending"],
        )
        for bot_key, counts in sorted(per_bot.items())
    ]
    return MonthlyReport(user_id=user_id, year=year, month=month, bot_stats=bot_stats)


async def generate_month_days_report(
    session: AsyncSession,
    user_id: int,
    year: int,
    month: int,
    bot_key: str | None = None,
) -> MonthDaysReport:
    """Return per-day scheduled/completed flags for a bot within a month.

    Completed days are those with at least one positive (POSITIVE) event.
    Scheduled days are those with at least one non-cancelled/suppressed event.
    """
    _, last_day = monthrange(year, month)
    month_start = date(year, month, 1)
    month_end = date(year, month, last_day) + timedelta(days=1)

    query = select(ReminderEvent).where(
        ReminderEvent.user_id == user_id,
        ReminderEvent.scheduled_local_date >= month_start,
        ReminderEvent.scheduled_local_date < month_end,
        ReminderEvent.status.notin_(
            [ReminderStatus.CANCELLED.value, ReminderStatus.SUPPRESSED.value]
        ),
    )
    if bot_key:
        query = query.where(ReminderEvent.bot_key == bot_key)
    result = await session.execute(query)
    events = list(result.scalars().all())

    scheduled = {event.scheduled_local_date for event in events}
    completed = {
        event.scheduled_local_date
        for event in events
        if event.status == ReminderStatus.POSITIVE.value
    }

    return MonthDaysReport(
        user_id=user_id,
        year=year,
        month=month,
        bot_key=bot_key,
        scheduled_days=sorted(scheduled),
        completed_days=sorted(completed),
    )


async def generate_yearly_report(
    session: AsyncSession,
    user_id: int,
    year: int,
) -> YearlyReport:
    """Generate a yearly completion report aggregated from 12 monthly reports."""
    monthly_breakdown: list[MonthlyBreakdown] = []
    for month in range(1, 13):
        monthly = await generate_monthly_report(session, user_id, year, month)
        monthly_breakdown.append(
            MonthlyBreakdown(
                month=month,
                total=monthly.total,
                completed=monthly.total_completed,
                missed=monthly.total_missed,
                snoozed=monthly.total_snoozed,
                pending=monthly.total_pending,
                completion_rate=monthly.completion_rate,
            )
        )
    return YearlyReport(user_id=user_id, year=year, monthly=monthly_breakdown)


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
    "BotMonthlyStats",
    "DailyReport",
    "MonthDaysReport",
    "MonthlyBreakdown",
    "MonthlyReport",
    "WeeklyReport",
    "YearlyReport",
    "generate_daily_report",
    "generate_month_days_report",
    "generate_monthly_report",
    "generate_weekly_report",
    "generate_yearly_report",
]
