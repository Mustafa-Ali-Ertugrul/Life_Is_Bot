from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone import now_in
from app.models import BotKey, ReminderEvent, ReminderStatus
from app.services import reminder_service, report_service, user_service
from app.services.event_labels import event_label
from tests.conftest import TELEGRAM_USER_ID


async def _user(db_session: AsyncSession) -> int:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    return user.id


async def _event(
    db_session: AsyncSession,
    user_id: int,
    *,
    scheduled_at: datetime,
    status: ReminderStatus = ReminderStatus.SCHEDULED,
    related_id: int = 1,
    label: str | None = None,
) -> ReminderEvent:
    interpretation = '{"habit_name": "' + label + '"}' if label is not None else "{}"
    event = await reminder_service.create_event(
        db_session,
        user_id=user_id,
        bot_key=BotKey.HABIT,
        scheduled_at=scheduled_at,
        related_type="habit",
        related_id=related_id,
        interpretation_json=interpretation,
    )
    event.status = status.value
    await db_session.commit()
    return event


def _today(hour: int = 8) -> datetime:
    return now_in().replace(hour=hour, minute=0, second=0, microsecond=0)


def _day_at(day_offset: int, hour: int = 8) -> datetime:
    return (_today() + timedelta(days=day_offset)).replace(hour=hour)


def _week_start() -> datetime:
    today = _today()
    return (today - timedelta(days=today.weekday())).replace(hour=0, minute=0, second=0)


def _monday_at(hour: int = 8) -> datetime:
    return _week_start().replace(hour=hour)


async def test_daily_report_counts_today(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _event(
        db_session,
        user_id,
        scheduled_at=_today(8),
        status=ReminderStatus.POSITIVE,
        related_id=1,
        label="Su iç",
    )
    await _event(
        db_session,
        user_id,
        scheduled_at=_today(9),
        status=ReminderStatus.NEGATIVE,
        related_id=2,
        label="Kitap oku",
    )
    await _event(
        db_session,
        user_id,
        scheduled_at=_today(10),
        status=ReminderStatus.SCHEDULED,
        related_id=3,
        label="Diş fırçala",
    )

    data = await report_service.generate_daily_report(db_session, user_id)

    assert data["total"] == 3
    assert data["completed"] == 1
    assert data["missed"] == 1
    assert data["unanswered"] == 1
    assert data["completed_items"] == ["Su iç"]
    assert data["missed_items"] == ["Kitap oku"]


async def test_daily_report_excludes_other_days(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _event(
        db_session, user_id, scheduled_at=_day_at(-1), status=ReminderStatus.POSITIVE, related_id=1
    )
    await _event(
        db_session, user_id, scheduled_at=_day_at(1), status=ReminderStatus.NEGATIVE, related_id=2
    )

    data = await report_service.generate_daily_report(db_session, user_id)

    assert data["total"] == 0
    assert data["completed"] == 0
    assert data["missed"] == 0
    assert data["unanswered"] == 0


async def test_daily_report_excludes_cancelled(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _event(
        db_session, user_id, scheduled_at=_today(8), status=ReminderStatus.CANCELLED, related_id=1
    )
    await _event(
        db_session,
        user_id,
        scheduled_at=_today(9),
        status=ReminderStatus.POSITIVE,
        related_id=2,
        label="Su iç",
    )

    data = await report_service.generate_daily_report(db_session, user_id)

    assert data["total"] == 1
    assert data["completed"] == 1
    assert data["missed"] == 0


async def test_daily_report_empty_day(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)

    data = await report_service.generate_daily_report(db_session, user_id)

    assert data["total"] == 0
    assert data["completed_items"] == []
    assert data["missed_items"] == []


async def test_weekly_report_counts_week_and_compliance(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _event(
        db_session,
        user_id,
        scheduled_at=_monday_at(8),
        status=ReminderStatus.POSITIVE,
        related_id=1,
        label="Su iç",
    )
    await _event(
        db_session,
        user_id,
        scheduled_at=_monday_at(9),
        status=ReminderStatus.NEGATIVE,
        related_id=2,
        label="Kitap oku",
    )
    await _event(
        db_session,
        user_id,
        scheduled_at=_monday_at(10) + timedelta(days=1),
        status=ReminderStatus.SCHEDULED,
        related_id=3,
        label="Diş fırçala",
    )
    await _event(
        db_session,
        user_id,
        scheduled_at=_monday_at(8) - timedelta(days=7),
        status=ReminderStatus.POSITIVE,
        related_id=4,
        label="Geçen hafta",
    )

    data = await report_service.generate_weekly_report(db_session, user_id)

    assert data["total"] == 3
    assert data["completed"] == 1
    assert data["missed"] == 1
    assert data["unanswered"] == 1
    assert data["compliance_rate"] == 33
    assert data["best_day"] == 1
    assert data["weakest_day"] == 2


async def test_weekly_report_best_weakest_days(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _event(
        db_session,
        user_id,
        scheduled_at=_monday_at(8),
        status=ReminderStatus.POSITIVE,
        related_id=1,
    )
    await _event(
        db_session,
        user_id,
        scheduled_at=_monday_at(9),
        status=ReminderStatus.POSITIVE,
        related_id=2,
    )
    await _event(
        db_session,
        user_id,
        scheduled_at=_monday_at(8) + timedelta(days=1),
        status=ReminderStatus.POSITIVE,
        related_id=3,
    )
    await _event(
        db_session,
        user_id,
        scheduled_at=_monday_at(9) + timedelta(days=1),
        status=ReminderStatus.NEGATIVE,
        related_id=4,
    )
    await _event(
        db_session,
        user_id,
        scheduled_at=_monday_at(8) + timedelta(days=2),
        status=ReminderStatus.NEGATIVE,
        related_id=5,
    )

    data = await report_service.generate_weekly_report(db_session, user_id)

    assert data["best_day"] == 1
    assert data["weakest_day"] == 3


async def test_weekly_report_empty_week(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)

    data = await report_service.generate_weekly_report(db_session, user_id)

    assert data["total"] == 0
    assert data["compliance_rate"] == 0
    assert data["best_day"] is None
    assert data["weakest_day"] is None


async def test_event_label_fallback() -> None:
    event = ReminderEvent(
        user_id=1,
        bot_key=BotKey.HABIT.value,
        related_type="habit",
        related_id=1,
        scheduled_at=datetime(2026, 8, 1, 8, 30),
        status=ReminderStatus.SCHEDULED.value,
        interpretation_json="{}",
        created_at=datetime(2026, 8, 1, 0, 0),
    )

    assert event_label(event) == "habit"


async def test_daily_report_uses_given_day(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    today = now_in().date()
    yesterday = today - timedelta(days=1)
    await _event(
        db_session,
        user_id,
        scheduled_at=datetime.combine(yesterday, time(8, 0), tzinfo=now_in().tzinfo),
        status=ReminderStatus.POSITIVE,
        related_id=1,
        label="Su iç",
    )

    data = await report_service.generate_daily_report(db_session, user_id, day=yesterday)

    assert data["total"] == 1
    assert data["completed"] == 1
    assert data["date"] == yesterday.isoformat()


async def test_daily_report_excludes_suppressed(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _event(db_session, user_id, scheduled_at=_today(), status=ReminderStatus.SUPPRESSED)

    data = await report_service.generate_daily_report(db_session, user_id)

    assert data["total"] == 0
    assert data["unanswered"] == 0


async def test_weekly_report_excludes_suppressed(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _event(
        db_session,
        user_id,
        scheduled_at=_monday_at(),
        status=ReminderStatus.SUPPRESSED,
    )

    data = await report_service.generate_weekly_report(db_session, user_id)

    assert data["total"] == 0
    assert data["unanswered"] == 0


async def test_daily_report_uses_local_date_not_scheduled_at(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    db_session.add(
        ReminderEvent(
            user_id=user_id,
            bot_key=BotKey.HABIT.value,
            related_type="habit",
            related_id=1,
            scheduled_at=datetime(2026, 8, 2, 2, 30, tzinfo=timezone.utc),
            scheduled_local_date=date(2026, 8, 1),
            dedupe_key="report-local-date-test",
            status=ReminderStatus.POSITIVE.value,
            interpretation_json='{"habit_name": "Su iç"}',
            created_at=datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc),
        )
    )
    await db_session.commit()

    data = await report_service.generate_daily_report(db_session, user_id, day=date(2026, 8, 1))

    assert data["total"] == 1
    assert data["completed"] == 1
    assert data["completed_items"] == ["Su iç"]


async def test_weekly_report_uses_local_date_range(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    week_start = date(2026, 8, 3)
    db_session.add(
        ReminderEvent(
            user_id=user_id,
            bot_key=BotKey.HABIT.value,
            related_type="habit",
            related_id=1,
            scheduled_at=datetime(2026, 8, 10, 2, 30, tzinfo=timezone.utc),
            scheduled_local_date=date(2026, 8, 4),
            dedupe_key="report-weekly-local-date-test",
            status=ReminderStatus.POSITIVE.value,
            interpretation_json="{}",
            created_at=datetime(2026, 8, 3, 0, 0, tzinfo=timezone.utc),
        )
    )
    await db_session.commit()

    data = await report_service.generate_weekly_report(
        db_session, user_id, week_start=week_start
    )

    assert data["total"] == 1
    assert data["completed"] == 1
    assert data["week_start"] == week_start.isoformat()
