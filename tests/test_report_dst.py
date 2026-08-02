from datetime import UTC, date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import report_service, step_service, user_service
from tests.conftest import TELEGRAM_USER_ID

NY = "America/New_York"

SPRING_DAY_UTC = datetime(2026, 3, 8, 5, 0, tzinfo=UTC)
FALL_DAY_UTC = datetime(2026, 11, 1, 4, 0, tzinfo=UTC)


async def _user(db_session: AsyncSession, timezone: str = NY) -> int:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    user.timezone = timezone
    await db_session.commit()
    return user.id


async def _step_event(
    db_session: AsyncSession, user_id: int, hour: int, minute: int, now: datetime
) -> None:
    settings = await step_service.get_or_create_settings(db_session, user_id)
    settings.reminder_hour = hour
    settings.reminder_minute = minute
    settings.days_of_week = "1,2,3,4,5,6,7"
    await db_session.commit()
    await step_service.generate_today_events(db_session, user_id, now=now)


async def test_report_includes_spring_forward_day_event(db_session: AsyncSession) -> None:
    user_id = await _user(db_session, NY)
    await _step_event(db_session, user_id, 2, 30, SPRING_DAY_UTC)

    report = await report_service.generate_monthly_report(db_session, user_id, 2026, 3)

    assert report.total == 1


async def test_report_includes_fall_back_day_event(db_session: AsyncSession) -> None:
    user_id = await _user(db_session, NY)
    await _step_event(db_session, user_id, 1, 30, FALL_DAY_UTC)

    report = await report_service.generate_monthly_report(db_session, user_id, 2026, 11)

    assert report.total == 1


async def test_report_excludes_previous_month(db_session: AsyncSession) -> None:
    user_id = await _user(db_session, NY)
    await _step_event(db_session, user_id, 8, 0, datetime(2026, 2, 28, 12, 0, tzinfo=UTC))

    report = await report_service.generate_monthly_report(db_session, user_id, 2026, 3)

    assert report.total == 0


async def test_report_scheduled_local_date_dst_independent(db_session: AsyncSession) -> None:
    user_id = await _user(db_session, NY)
    settings = await step_service.get_or_create_settings(db_session, user_id)
    settings.reminder_hour = 2
    settings.reminder_minute = 30
    await db_session.commit()
    events = await step_service.generate_today_events(db_session, user_id, now=SPRING_DAY_UTC)

    assert events[0].scheduled_local_date == date(2026, 3, 8)


async def test_report_empty_dst_month(db_session: AsyncSession) -> None:
    user_id = await _user(db_session, NY)

    report = await report_service.generate_monthly_report(db_session, user_id, 2026, 3)

    assert report.total == 0
