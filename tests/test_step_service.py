from datetime import UTC, date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidStateError
from app.core.timezone import get_user_timezone, now_in
from app.models import BotKey
from app.services import preference_service, step_service, user_service
from tests.conftest import TELEGRAM_USER_ID


async def _user(db_session: AsyncSession) -> int:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    return user.id


async def test_get_or_create_settings_creates_defaults(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)

    settings = await step_service.get_or_create_settings(db_session, user_id)

    assert settings.daily_target == 8000
    assert settings.reminder_hour == 21
    assert settings.reminder_minute == 0
    assert settings.days_of_week == "1,2,3,4,5,6,7"
    assert settings.is_active is True


async def test_get_or_create_settings_returns_existing(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    first = await step_service.get_or_create_settings(db_session, user_id)

    second = await step_service.get_or_create_settings(db_session, user_id)

    assert second.id == first.id


async def test_get_or_create_settings_enables_step_preference(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session)

    settings = await step_service.get_or_create_settings(db_session, user_id)

    pref = await preference_service.get_preference(db_session, settings.user_id, BotKey.STEP)
    assert pref is not None
    assert pref.enabled is True


async def test_get_settings_none_when_missing(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)

    settings = await step_service.get_settings(db_session, user_id)

    assert settings is None


async def test_update_daily_target(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await step_service.get_or_create_settings(db_session, user_id)

    settings = await step_service.update_daily_target(db_session, user_id, 12000)

    assert settings.daily_target == 12000


@pytest.mark.parametrize("bad_target", [-1, 100001])
async def test_update_daily_target_rejects_out_of_range(
    db_session: AsyncSession, bad_target: int
) -> None:
    user_id = await _user(db_session)

    with pytest.raises(InvalidStateError):
        await step_service.update_daily_target(db_session, user_id, bad_target)


async def test_update_reminder_time(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await step_service.get_or_create_settings(db_session, user_id)

    settings = await step_service.update_reminder_time(db_session, user_id, 8, 30)

    assert settings.reminder_hour == 8
    assert settings.reminder_minute == 30


@pytest.mark.parametrize("bad_hour, bad_minute", [(24, 0), (8, 60)])
async def test_update_reminder_time_rejects_invalid(
    db_session: AsyncSession, bad_hour: int, bad_minute: int
) -> None:
    user_id = await _user(db_session)

    with pytest.raises(InvalidStateError):
        await step_service.update_reminder_time(db_session, user_id, bad_hour, bad_minute)


async def test_toggle_step_bot(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    settings = await step_service.get_or_create_settings(db_session, user_id)

    updated = await step_service.toggle_step_bot(db_session, user_id, False)

    assert updated.is_active is False
    assert updated.id == settings.id


async def test_log_steps_creates_new_record(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    today = now_in().date()

    log = await step_service.log_steps(db_session, user_id, 7850, today)

    assert log.user_id == user_id
    assert log.log_date == today
    assert log.steps == 7850
    assert log.source == "manual"


async def test_log_steps_updates_same_day(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    today = now_in().date()
    await step_service.log_steps(db_session, user_id, 7000, today)

    log = await step_service.log_steps(db_session, user_id, 8500, today)

    assert log.steps == 8500
    logs = await step_service.get_steps_for_date(db_session, user_id, today)
    assert logs is not None
    assert logs.steps == 8500


@pytest.mark.parametrize("bad_steps", [-1, 200001])
async def test_log_steps_rejects_out_of_range(db_session: AsyncSession, bad_steps: int) -> None:
    user_id = await _user(db_session)

    with pytest.raises(InvalidStateError):
        await step_service.log_steps(db_session, user_id, bad_steps, now_in().date())


async def test_get_steps_for_date(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    today = now_in().date()
    await step_service.log_steps(db_session, user_id, 6000, today)

    found = await step_service.get_steps_for_date(db_session, user_id, today)
    missing = await step_service.get_steps_for_date(db_session, user_id, date(2026, 1, 1))

    assert found is not None
    assert found.steps == 6000
    assert missing is None


async def test_get_today_steps(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    today = now_in().date()
    await step_service.log_steps(db_session, user_id, 9000, today)

    found = await step_service.get_today_steps(db_session, user_id)

    assert found is not None
    assert found.steps == 9000


async def test_generate_today_events_creates_for_matching_day(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session)
    today = now_in()
    settings = await step_service.get_or_create_settings(db_session, user_id)

    events = await step_service.generate_today_events(db_session, user_id, now=today)

    assert len(events) == 1
    event = events[0]
    assert event.bot_key == BotKey.STEP.value
    assert event.related_type == "step_goal"
    assert event.related_id == settings.id
    assert (
        event.scheduled_at.replace(tzinfo=UTC).astimezone(get_user_timezone("Europe/Istanbul")).hour
        == 21
    )
    assert event.scheduled_local_date == today.date()
    assert '"daily_target": 8000' in event.interpretation_json


async def test_generate_today_events_no_settings_returns_empty(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session)

    events = await step_service.generate_today_events(db_session, user_id)

    assert events == []


async def test_generate_today_events_skips_inactive(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    today = now_in()
    await step_service.get_or_create_settings(db_session, user_id)
    await step_service.toggle_step_bot(db_session, user_id, False)

    events = await step_service.generate_today_events(db_session, user_id, now=today)

    assert events == []


async def test_generate_today_events_skips_non_matching_day(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session)
    today = now_in()
    other_weekday = (today.isoweekday() % 7) + 1
    settings = await step_service.get_or_create_settings(db_session, user_id)
    settings.days_of_week = str(other_weekday)
    await db_session.commit()

    events = await step_service.generate_today_events(db_session, user_id, now=today)

    assert events == []


async def test_generate_today_events_is_idempotent(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    today = now_in()
    await step_service.get_or_create_settings(db_session, user_id)

    first = await step_service.generate_today_events(db_session, user_id, now=today)
    second = await step_service.generate_today_events(db_session, user_id, now=today)

    assert len(first) == 1
    assert len(second) == 1
    assert second[0].id == first[0].id
