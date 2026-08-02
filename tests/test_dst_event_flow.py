from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.notification_policy import evaluate_notification
from app.models import ReminderEvent, User
from app.services import report_service, step_service, user_service
from tests.conftest import TELEGRAM_USER_ID

NY = "America/New_York"
IST = "Europe/Istanbul"

SPRING_DAY_UTC = datetime(2026, 3, 8, 5, 0, tzinfo=UTC)
FALL_DAY_UTC = datetime(2026, 11, 1, 4, 0, tzinfo=UTC)


async def _user(db_session: AsyncSession, timezone: str = NY) -> User:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    user.timezone = timezone
    user.is_active = True
    user.consent_given = True
    user.notifications_enabled = True
    await db_session.commit()
    return user


async def _step_event(
    db_session: AsyncSession,
    user_id: int,
    hour: int,
    minute: int,
    now: datetime,
) -> ReminderEvent:
    settings = await step_service.get_or_create_settings(db_session, user_id)
    settings.reminder_hour = hour
    settings.reminder_minute = minute
    await db_session.commit()
    events = await step_service.generate_today_events(db_session, user_id, now=now)
    return events[0]


async def test_flow_spring_forward_event_uses_edt_offset(db_session: AsyncSession) -> None:
    user = await _user(db_session, NY)
    event = await _step_event(db_session, user.id, 2, 30, SPRING_DAY_UTC)

    assert event.scheduled_at == datetime(2026, 3, 8, 7, 30)
    decision = await evaluate_notification(
        db_session, user, event, datetime(2026, 3, 8, 7, 30, tzinfo=UTC)
    )
    assert decision["action"] == "send_now"


async def test_flow_fall_back_single_event(db_session: AsyncSession) -> None:
    user = await _user(db_session, NY)
    event = await _step_event(db_session, user.id, 1, 30, FALL_DAY_UTC)

    result = await db_session.execute(
        select(func.count()).select_from(ReminderEvent).where(ReminderEvent.user_id == user.id)
    )
    assert result.scalar_one() == 1
    assert event.scheduled_at == datetime(2026, 11, 1, 5, 30)


async def test_flow_quiet_hours_independent_of_dst(db_session: AsyncSession) -> None:
    user = await _user(db_session, NY)
    user.quiet_hours_enabled = True
    user.quiet_hours_start = "00:00"
    user.quiet_hours_end = "03:00"
    await db_session.commit()
    event = await _step_event(db_session, user.id, 1, 30, FALL_DAY_UTC)

    decision = await evaluate_notification(
        db_session, user, event, datetime(2026, 11, 1, 5, 30, tzinfo=UTC)
    )

    assert decision["action"] == "defer"
    assert decision["reason"] == "quiet_hours"


async def test_flow_istanbul_baseline(db_session: AsyncSession) -> None:
    user = await _user(db_session, IST)
    event = await _step_event(db_session, user.id, 8, 0, datetime(2026, 7, 15, 6, 0, tzinfo=UTC))

    assert event.scheduled_at == datetime(2026, 7, 15, 5, 0)
    decision = await evaluate_notification(
        db_session, user, event, datetime(2026, 7, 15, 5, 0, tzinfo=UTC)
    )
    assert decision["action"] == "send_now"
    report = await report_service.generate_monthly_report(db_session, user.id, 2026, 7)
    assert report.total == 1
