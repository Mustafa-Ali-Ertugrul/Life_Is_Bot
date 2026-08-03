from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone import now_in
from app.models import BotKey, ReminderEvent, ReminderStatus
from app.services import streak_service, user_service
from app.services.streak_service import (
    LOOKBACK_DAYS,
    calculate_longest_streak,
    calculate_streak,
)
from tests.conftest import TELEGRAM_USER_ID


async def _user(db_session: AsyncSession) -> tuple[int, str]:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    return user.id, user.timezone


async def _event(
    db_session: AsyncSession,
    user_id: int,
    local_date: date,
    *,
    status: ReminderStatus = ReminderStatus.POSITIVE,
    related_id: int = 1,
    commit: bool = True,
) -> None:
    db_session.add(
        ReminderEvent(
            user_id=user_id,
            bot_key=BotKey.HABIT.value,
            related_type="habit",
            related_id=related_id,
            scheduled_at=datetime.combine(local_date, time(8, 0), tzinfo=UTC),
            scheduled_local_date=local_date,
            dedupe_key=f"streak-{local_date.isoformat()}-{status.value}-{related_id}",
            status=status.value,
            interpretation_json="{}",
            created_at=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
        )
    )
    if commit:
        await db_session.commit()


def test_calculate_streak_empty() -> None:
    assert calculate_streak(set(), date(2026, 8, 3)) == 0


def test_calculate_streak_today_completed() -> None:
    today = date(2026, 8, 3)
    days = {today, today - timedelta(days=1), today - timedelta(days=2)}

    assert calculate_streak(days, today) == 3


def test_calculate_streak_today_pending_continues_yesterday() -> None:
    today = date(2026, 8, 3)
    days = {today - timedelta(days=1), today - timedelta(days=2)}

    assert calculate_streak(days, today) == 2


def test_calculate_streak_breaks_on_gap() -> None:
    today = date(2026, 8, 3)
    days = {today, today - timedelta(days=2)}

    assert calculate_streak(days, today) == 1


def test_calculate_streak_pending_and_yesterday_missing() -> None:
    today = date(2026, 8, 3)
    days = {today - timedelta(days=3)}

    assert calculate_streak(days, today) == 0


def test_calculate_longest_streak_empty() -> None:
    assert calculate_longest_streak(set()) == 0


def test_calculate_longest_streak_single_day() -> None:
    assert calculate_longest_streak({date(2026, 8, 1)}) == 1


def test_calculate_longest_streak_sequence() -> None:
    start = date(2026, 1, 1)
    days = {start + timedelta(days=i) for i in range(10)}

    assert calculate_longest_streak(days) == 10


def test_calculate_longest_streak_with_gaps() -> None:
    days = {
        date(2026, 8, 1),
        date(2026, 8, 2),
        date(2026, 8, 3),
        date(2026, 8, 10),
        date(2026, 8, 11),
    }

    assert calculate_longest_streak(days) == 3


def test_calculate_longest_streak_out_of_order() -> None:
    days = {date(2026, 8, 3), date(2026, 8, 1), date(2026, 8, 2)}

    assert calculate_longest_streak(days) == 3


async def test_streak_report_empty(db_session: AsyncSession) -> None:
    user_id, _ = await _user(db_session)

    report = await streak_service.generate_streak_report(db_session, user_id)

    assert report.user_id == user_id
    assert report.current == 0
    assert report.longest == 0
    assert report.today_completed is False


async def test_streak_report_consecutive_days(db_session: AsyncSession) -> None:
    user_id, timezone = await _user(db_session)
    today = now_in(timezone).date()
    for offset in range(3):
        await _event(db_session, user_id, today - timedelta(days=offset), related_id=offset + 1)

    report = await streak_service.generate_streak_report(db_session, user_id)

    assert report.current == 3
    assert report.longest == 3
    assert report.today_completed is True


async def test_streak_report_pending_today_uses_yesterday(db_session: AsyncSession) -> None:
    user_id, timezone = await _user(db_session)
    today = now_in(timezone).date()
    await _event(db_session, user_id, today - timedelta(days=1), related_id=1)
    await _event(db_session, user_id, today, status=ReminderStatus.SCHEDULED, related_id=2)

    report = await streak_service.generate_streak_report(db_session, user_id)

    assert report.current == 1
    assert report.longest == 1
    assert report.today_completed is False


async def test_streak_report_longest_exceeds_current(db_session: AsyncSession) -> None:
    user_id, timezone = await _user(db_session)
    today = now_in(timezone).date()
    for offset in (6, 5, 4, 3):
        await _event(db_session, user_id, today - timedelta(days=offset), related_id=offset)
    await _event(
        db_session,
        user_id,
        today - timedelta(days=2),
        status=ReminderStatus.NEGATIVE,
        related_id=20,
    )
    for offset in (1, 0):
        await _event(db_session, user_id, today - timedelta(days=offset), related_id=offset)

    report = await streak_service.generate_streak_report(db_session, user_id)

    assert report.current == 2
    assert report.longest == 4
    assert report.today_completed is True


async def test_streak_report_excludes_cancelled_and_suppressed(
    db_session: AsyncSession,
) -> None:
    user_id, timezone = await _user(db_session)
    today = now_in(timezone).date()
    await _event(db_session, user_id, today, related_id=1)
    await _event(
        db_session,
        user_id,
        today - timedelta(days=1),
        status=ReminderStatus.CANCELLED,
        related_id=2,
    )
    await _event(
        db_session,
        user_id,
        today - timedelta(days=2),
        status=ReminderStatus.SUPPRESSED,
        related_id=3,
    )

    report = await streak_service.generate_streak_report(db_session, user_id)

    assert report.current == 1
    assert report.longest == 1
    assert report.today_completed is True


async def test_streak_report_partial_day_not_completed(db_session: AsyncSession) -> None:
    user_id, timezone = await _user(db_session)
    today = now_in(timezone).date()
    await _event(db_session, user_id, today, related_id=1)
    await _event(db_session, user_id, today, status=ReminderStatus.NO_RESPONSE, related_id=2)

    report = await streak_service.generate_streak_report(db_session, user_id)

    assert report.current == 0
    assert report.longest == 0
    assert report.today_completed is False


async def test_streak_report_capped_at_lookback(db_session: AsyncSession) -> None:
    assert LOOKBACK_DAYS == 365
    user_id, timezone = await _user(db_session)
    today = now_in(timezone).date()
    for offset in range(LOOKBACK_DAYS):
        await _event(
            db_session,
            user_id,
            today - timedelta(days=offset),
            related_id=offset + 1,
            commit=False,
        )
    await _event(
        db_session,
        user_id,
        today - timedelta(days=LOOKBACK_DAYS),
        related_id=999,
        commit=False,
    )
    await db_session.commit()

    report = await streak_service.generate_streak_report(db_session, user_id)

    assert report.current == LOOKBACK_DAYS
    assert report.longest == LOOKBACK_DAYS
