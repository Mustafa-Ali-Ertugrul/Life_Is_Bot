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
        dedupe_key=f"monthly-{local_date.isoformat()}-{bot_key.value}-{related_id}",
        status=status.value,
        interpretation_json="{}",
        created_at=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
    )
    db_session.add(event)
    await db_session.commit()
    return event


async def test_monthly_report_empty_month(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)

    report = await report_service.generate_monthly_report(db_session, user_id, 2026, 8)

    assert report.total == 0
    assert report.bot_stats == []
    assert report.completion_rate == 0.0


async def test_monthly_report_counts_completed(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _event(db_session, user_id, date(2026, 8, 15), status=ReminderStatus.POSITIVE)

    report = await report_service.generate_monthly_report(db_session, user_id, 2026, 8)

    assert report.total == 1
    assert report.total_completed == 1
    assert report.completion_rate == 100.0
    stats = report.bot_stats[0]
    assert stats.bot_key == BotKey.HABIT.value
    assert stats.completed == 1
    assert stats.completion_rate == 100.0


async def test_monthly_report_counts_missed(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _event(db_session, user_id, date(2026, 8, 15), status=ReminderStatus.NEGATIVE)

    report = await report_service.generate_monthly_report(db_session, user_id, 2026, 8)

    assert report.total == 1
    assert report.total_missed == 1
    assert report.completion_rate == 0.0


async def test_monthly_report_counts_snoozed(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _event(db_session, user_id, date(2026, 8, 15), status=ReminderStatus.SNOOZED)

    report = await report_service.generate_monthly_report(db_session, user_id, 2026, 8)

    assert report.total == 1
    assert report.total_snoozed == 1


async def test_monthly_report_counts_pending(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _event(db_session, user_id, date(2026, 8, 15), status=ReminderStatus.SCHEDULED)

    report = await report_service.generate_monthly_report(db_session, user_id, 2026, 8)

    assert report.total == 1
    assert report.total_pending == 1


async def test_monthly_report_excludes_cancelled(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _event(db_session, user_id, date(2026, 8, 15), status=ReminderStatus.CANCELLED)
    await _event(
        db_session,
        user_id,
        date(2026, 8, 16),
        status=ReminderStatus.POSITIVE,
        related_id=2,
    )

    report = await report_service.generate_monthly_report(db_session, user_id, 2026, 8)

    assert report.total == 1
    assert report.total_completed == 1


async def test_monthly_report_excludes_suppressed(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _event(db_session, user_id, date(2026, 8, 15), status=ReminderStatus.SUPPRESSED)

    report = await report_service.generate_monthly_report(db_session, user_id, 2026, 8)

    assert report.total == 0
    assert report.total_pending == 0


async def test_monthly_report_multi_bot_breakdown(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _event(
        db_session,
        user_id,
        date(2026, 8, 1),
        bot_key=BotKey.HABIT,
        status=ReminderStatus.POSITIVE,
    )
    await _event(
        db_session,
        user_id,
        date(2026, 8, 2),
        bot_key=BotKey.SPORT,
        status=ReminderStatus.NEGATIVE,
        related_id=2,
    )
    await _event(
        db_session,
        user_id,
        date(2026, 8, 3),
        bot_key=BotKey.MEDICATION,
        status=ReminderStatus.POSITIVE,
        related_id=3,
    )
    await _event(
        db_session,
        user_id,
        date(2026, 8, 4),
        bot_key=BotKey.STEP,
        status=ReminderStatus.SCHEDULED,
        related_id=4,
    )

    report = await report_service.generate_monthly_report(db_session, user_id, 2026, 8)

    assert report.total == 4
    assert report.total_completed == 2
    assert report.total_missed == 1
    assert report.total_pending == 1
    assert report.completion_rate == 50.0
    assert [s.bot_key for s in report.bot_stats] == [
        BotKey.HABIT.value,
        BotKey.MEDICATION.value,
        BotKey.SPORT.value,
        BotKey.STEP.value,
    ]
    by_key = {s.bot_key: s for s in report.bot_stats}
    assert by_key[BotKey.HABIT.value].completed == 1
    assert by_key[BotKey.SPORT.value].missed == 1
    assert by_key[BotKey.STEP.value].pending == 1


async def test_monthly_report_excludes_previous_month(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _event(db_session, user_id, date(2026, 7, 31), status=ReminderStatus.POSITIVE)

    report = await report_service.generate_monthly_report(db_session, user_id, 2026, 8)

    assert report.total == 0


async def test_monthly_report_excludes_next_month(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _event(
        db_session,
        user_id,
        date(2026, 8, 15),
        status=ReminderStatus.POSITIVE,
        related_id=1,
    )
    await _event(
        db_session,
        user_id,
        date(2026, 9, 1),
        status=ReminderStatus.POSITIVE,
        related_id=2,
    )

    report = await report_service.generate_monthly_report(db_session, user_id, 2026, 8)

    assert report.total == 1


async def test_monthly_report_includes_last_day_of_month(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _event(db_session, user_id, date(2026, 8, 31), status=ReminderStatus.POSITIVE)

    report = await report_service.generate_monthly_report(db_session, user_id, 2026, 8)

    assert report.total == 1


async def test_monthly_report_february_not_leap(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _event(
        db_session,
        user_id,
        date(2026, 2, 28),
        status=ReminderStatus.POSITIVE,
        related_id=1,
    )
    await _event(
        db_session,
        user_id,
        date(2026, 3, 1),
        status=ReminderStatus.NEGATIVE,
        related_id=2,
    )

    report = await report_service.generate_monthly_report(db_session, user_id, 2026, 2)

    assert report.total == 1
    assert report.total_completed == 1


async def test_monthly_report_december_january_boundary(db_session: AsyncSession) -> None:
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

    december = await report_service.generate_monthly_report(db_session, user_id, 2026, 12)
    january = await report_service.generate_monthly_report(db_session, user_id, 2027, 1)

    assert december.total == 1
    assert december.total_completed == 1
    assert january.total == 1
    assert january.total_missed == 1
