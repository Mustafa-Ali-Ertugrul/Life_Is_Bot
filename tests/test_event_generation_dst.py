from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ReminderEvent
from app.services import step_service, user_service
from tests.conftest import TELEGRAM_USER_ID

NY = "America/New_York"
IST = "Europe/Istanbul"

# UTC instants representing the start of the local DST day in New York:
# spring-forward 2026-03-08 starts at 00:00 EST == 05:00 UTC
# fall-back 2026-11-01 starts at 00:00 EDT == 04:00 UTC
SPRING_DAY_UTC = datetime(2026, 3, 8, 5, 0, tzinfo=UTC)
FALL_DAY_UTC = datetime(2026, 11, 1, 4, 0, tzinfo=UTC)


async def _user(db_session: AsyncSession, timezone: str = IST) -> int:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    user.timezone = timezone
    await db_session.commit()
    return user.id


async def _step_settings(db_session: AsyncSession, user_id: int, hour: int, minute: int) -> None:
    settings = await step_service.get_or_create_settings(db_session, user_id)
    settings.reminder_hour = hour
    settings.reminder_minute = minute
    settings.days_of_week = "1,2,3,4,5,6,7"
    settings.is_active = True
    await db_session.commit()


async def _generate(db_session: AsyncSession, user_id: int, now: datetime) -> list[ReminderEvent]:
    return await step_service.generate_today_events(db_session, user_id, now=now)


async def test_step_event_normal_day_summer(db_session: AsyncSession) -> None:
    user_id = await _user(db_session, NY)
    await _step_settings(db_session, user_id, 8, 0)

    events = await _generate(db_session, user_id, datetime(2026, 7, 15, 6, 0, tzinfo=UTC))

    assert len(events) == 1
    assert events[0].scheduled_at == datetime(2026, 7, 15, 12, 0)
    assert events[0].scheduled_local_date == date(2026, 7, 15)


async def test_step_event_normal_day_winter(db_session: AsyncSession) -> None:
    user_id = await _user(db_session, NY)
    await _step_settings(db_session, user_id, 8, 0)

    events = await _generate(db_session, user_id, datetime(2026, 1, 15, 12, 0, tzinfo=UTC))

    assert len(events) == 1
    assert events[0].scheduled_at == datetime(2026, 1, 15, 13, 0)
    assert events[0].scheduled_local_date == date(2026, 1, 15)


async def test_step_event_istanbul_no_dst(db_session: AsyncSession) -> None:
    user_id = await _user(db_session, IST)
    await _step_settings(db_session, user_id, 8, 0)

    events = await _generate(db_session, user_id, datetime(2026, 7, 15, 6, 0, tzinfo=UTC))

    assert len(events) == 1
    assert events[0].scheduled_at == datetime(2026, 7, 15, 5, 0)


async def test_step_event_spring_forward_shifts_to_0330_edt(db_session: AsyncSession) -> None:
    user_id = await _user(db_session, NY)
    await _step_settings(db_session, user_id, 2, 30)

    events = await _generate(db_session, user_id, SPRING_DAY_UTC)

    assert len(events) == 1
    assert events[0].scheduled_at == datetime(2026, 3, 8, 7, 30)
    assert events[0].scheduled_local_date == date(2026, 3, 8)


async def test_step_event_spring_forward_dedupe_key_uses_local_date(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session, NY)
    await _step_settings(db_session, user_id, 2, 30)

    first = await _generate(db_session, user_id, SPRING_DAY_UTC)
    second = await _generate(db_session, user_id, SPRING_DAY_UTC)

    assert first[0].id == second[0].id
    assert first[0].dedupe_key == second[0].dedupe_key


async def test_step_event_fall_back_fold0_first_occurrence(db_session: AsyncSession) -> None:
    user_id = await _user(db_session, NY)
    await _step_settings(db_session, user_id, 1, 30)

    events = await _generate(db_session, user_id, FALL_DAY_UTC)

    assert len(events) == 1
    assert events[0].scheduled_at == datetime(2026, 11, 1, 5, 30)
    assert events[0].scheduled_local_date == date(2026, 11, 1)


async def test_step_event_scheduled_local_date_spring_forward_day(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session, NY)
    await _step_settings(db_session, user_id, 2, 30)

    events = await _generate(db_session, user_id, SPRING_DAY_UTC)

    assert events[0].scheduled_local_date == date(2026, 3, 8)


async def test_step_event_scheduled_local_date_fall_back_day(db_session: AsyncSession) -> None:
    user_id = await _user(db_session, NY)
    await _step_settings(db_session, user_id, 1, 30)

    events = await _generate(db_session, user_id, FALL_DAY_UTC)

    assert events[0].scheduled_local_date == date(2026, 11, 1)


async def test_reminder_create_event_idempotent_dst_day(db_session: AsyncSession) -> None:
    user_id = await _user(db_session, NY)
    await _step_settings(db_session, user_id, 2, 30)

    await _generate(db_session, user_id, SPRING_DAY_UTC)
    await _generate(db_session, user_id, SPRING_DAY_UTC)

    result = await db_session.execute(
        select(func.count()).select_from(ReminderEvent).where(ReminderEvent.user_id == user_id)
    )
    assert result.scalar_one() == 1


async def test_step_event_inactive_setting_returns_empty(db_session: AsyncSession) -> None:
    user_id = await _user(db_session, NY)
    settings = await step_service.get_or_create_settings(db_session, user_id)
    settings.is_active = False
    await db_session.commit()

    events = await _generate(db_session, user_id, SPRING_DAY_UTC)

    assert events == []
