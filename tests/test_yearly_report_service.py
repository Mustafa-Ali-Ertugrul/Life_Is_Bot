from datetime import UTC, date, datetime, time

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BotKey, ReminderEvent, ReminderStatus
from app.services import report_service, user_service
from tests.conftest import TELEGRAM_USER_ID


async def _user(db_session: AsyncSession) -> int:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    return user.id


async def _event(
    db_session: AsyncSession,
    user_id: int,
    local_date: date,
    *,
    bot_key: BotKey = BotKey.HABIT,
    status: ReminderStatus = ReminderStatus.SCHEDULED,
    related_id: int = 1,
) -> ReminderEvent:
    event = ReminderEvent(
        user_id=user_id,
        bot_key=bot_key.value,
        related_type="habit",
        related_id=related_id,
        scheduled_at=datetime.combine(local_date, time(8, 0), tzinfo=UTC),
        scheduled_local_date=local_date,
        dedupe_key=f"yearly-{local_date.isoformat()}-{bot_key.value}-{related_id}",
        status=status.value,
        interpretation_json="{}",
        created_at=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
    )
    db_session.add(event)
    await db_session.commit()
    return event


async def test_yearly_report_empty_year(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)

    report = await report_service.generate_yearly_report(db_session, user_id, 2026)

    assert report.total == 0
    assert report.completion_rate == 0.0
    assert report.best_month is None
    assert report.worst_month is None
    assert len(report.monthly) == 12
    assert all(m.total == 0 for m in report.monthly)


async def test_yearly_report_aggregates_months(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _event(db_session, user_id, date(2026, 3, 10), status=ReminderStatus.POSITIVE)
    await _event(
        db_session,
        user_id,
        date(2026, 8, 15),
        status=ReminderStatus.NEGATIVE,
        related_id=2,
    )
    await _event(
        db_session,
        user_id,
        date(2026, 8, 16),
        status=ReminderStatus.POSITIVE,
        related_id=3,
    )

    report = await report_service.generate_yearly_report(db_session, user_id, 2026)

    assert report.total == 3
    assert report.total_completed == 2
    assert report.total_missed == 1
    assert report.completion_rate == round(2 * 100 / 3, 1)
    assert report.monthly[2].total == 1
    assert report.monthly[7].total == 2
    assert report.monthly[0].total == 0


async def test_yearly_report_partial_year(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _event(db_session, user_id, date(2026, 1, 5), status=ReminderStatus.POSITIVE)

    report = await report_service.generate_yearly_report(db_session, user_id, 2026)

    assert report.total == 1
    assert sum(1 for m in report.monthly if m.total > 0) == 1


async def test_yearly_report_best_month(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _event(db_session, user_id, date(2026, 1, 5), status=ReminderStatus.POSITIVE)
    await _event(
        db_session,
        user_id,
        date(2026, 2, 5),
        status=ReminderStatus.POSITIVE,
        related_id=2,
    )
    await _event(
        db_session,
        user_id,
        date(2026, 2, 6),
        status=ReminderStatus.NEGATIVE,
        related_id=3,
    )

    report = await report_service.generate_yearly_report(db_session, user_id, 2026)

    assert report.best_month is not None
    assert report.best_month.month == 1
    assert report.best_month.completion_rate == 100.0


async def test_yearly_report_worst_month(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _event(db_session, user_id, date(2026, 1, 5), status=ReminderStatus.POSITIVE)
    await _event(
        db_session,
        user_id,
        date(2026, 2, 5),
        status=ReminderStatus.NEGATIVE,
        related_id=2,
    )
    await _event(
        db_session,
        user_id,
        date(2026, 2, 6),
        status=ReminderStatus.POSITIVE,
        related_id=3,
    )

    report = await report_service.generate_yearly_report(db_session, user_id, 2026)

    assert report.worst_month is not None
    assert report.worst_month.month == 2
    assert report.worst_month.completion_rate == 50.0


async def test_yearly_report_best_worst_exclude_empty_months(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session)
    await _event(
        db_session,
        user_id,
        date(2026, 6, 5),
        status=ReminderStatus.NEGATIVE,
        related_id=1,
    )

    report = await report_service.generate_yearly_report(db_session, user_id, 2026)

    assert report.best_month is not None
    assert report.best_month.month == 6
    assert report.best_month.completion_rate == 0.0
    assert report.worst_month is not None
    assert report.worst_month.month == 6


async def test_yearly_report_leap_year(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _event(db_session, user_id, date(2028, 2, 29), status=ReminderStatus.POSITIVE)

    report = await report_service.generate_yearly_report(db_session, user_id, 2028)

    assert report.total == 1
    assert report.monthly[1].total == 1
    assert report.monthly[1].completed == 1


async def test_yearly_report_future_year_empty(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _event(db_session, user_id, date(2026, 1, 5), status=ReminderStatus.POSITIVE)

    report = await report_service.generate_yearly_report(db_session, user_id, 2027)

    assert report.total == 0
    assert report.best_month is None


async def test_yearly_report_year_boundary(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _event(
        db_session,
        user_id,
        date(2026, 12, 31),
        status=ReminderStatus.POSITIVE,
        related_id=1,
    )
    await _event(
        db_session,
        user_id,
        date(2027, 1, 1),
        status=ReminderStatus.NEGATIVE,
        related_id=2,
    )

    report = await report_service.generate_yearly_report(db_session, user_id, 2026)

    assert report.total == 1
    assert report.total_completed == 1
    assert report.monthly[11].total == 1
