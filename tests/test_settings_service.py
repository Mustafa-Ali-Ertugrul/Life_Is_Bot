import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.services import settings_service, user_service
from tests.conftest import TELEGRAM_USER_ID


async def _user(db_session: AsyncSession) -> User:
    return await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)


async def test_default_settings(db_session: AsyncSession) -> None:
    user = await _user(db_session)

    assert user.notifications_enabled is True
    assert user.quiet_hours_enabled is False
    assert user.quiet_hours_start is None
    assert user.quiet_hours_end is None
    assert user.week_start_day == 1


async def test_get_settings_raises_for_missing_user(db_session: AsyncSession) -> None:
    with pytest.raises(ValueError):
        await settings_service.get_settings(db_session, 999_999)


def test_is_valid_timezone() -> None:
    assert settings_service.is_valid_timezone("Europe/Istanbul") is True
    assert settings_service.is_valid_timezone("America/New_York") is True
    assert settings_service.is_valid_timezone("Mars/Olympus") is False
    assert settings_service.is_valid_timezone("") is False


def test_is_valid_hhmm() -> None:
    assert settings_service.is_valid_hhmm("23:00") is True
    assert settings_service.is_valid_hhmm("07:05") is True
    assert settings_service.is_valid_hhmm("7:00") is False
    assert settings_service.is_valid_hhmm("24:00") is False
    assert settings_service.is_valid_hhmm("23:60") is False
    assert settings_service.is_valid_hhmm("abc") is False


async def test_update_timezone_valid(db_session: AsyncSession) -> None:
    user = await _user(db_session)

    updated = await settings_service.update_timezone(db_session, user.id, "Europe/Paris")

    assert updated.timezone == "Europe/Paris"
    assert user.timezone == "Europe/Paris"


async def test_update_timezone_invalid_raises(db_session: AsyncSession) -> None:
    user = await _user(db_session)

    with pytest.raises(ValueError):
        await settings_service.update_timezone(db_session, user.id, "Mars/Olympus")

    assert user.timezone == "Europe/Istanbul"


async def test_toggle_notifications_flips_and_persists(db_session: AsyncSession) -> None:
    user = await _user(db_session)

    enabled = await settings_service.toggle_notifications(db_session, user.id)
    assert enabled is False
    assert user.notifications_enabled is False

    enabled = await settings_service.toggle_notifications(db_session, user.id)
    assert enabled is True
    assert user.notifications_enabled is True


async def test_set_quiet_hours_valid(db_session: AsyncSession) -> None:
    user = await _user(db_session)

    updated = await settings_service.set_quiet_hours(db_session, user.id, "23:00", "07:00")

    assert updated.quiet_hours_enabled is True
    assert updated.quiet_hours_start == "23:00"
    assert updated.quiet_hours_end == "07:00"


async def test_set_quiet_hours_invalid_raises(db_session: AsyncSession) -> None:
    user = await _user(db_session)

    with pytest.raises(ValueError):
        await settings_service.set_quiet_hours(db_session, user.id, "23:00", "07:60")
    with pytest.raises(ValueError):
        await settings_service.set_quiet_hours(db_session, user.id, "24:00", "07:00")

    assert user.quiet_hours_enabled is False
    assert user.quiet_hours_start is None


async def test_clear_quiet_hours(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    await settings_service.set_quiet_hours(db_session, user.id, "23:00", "07:00")

    updated = await settings_service.clear_quiet_hours(db_session, user.id)

    assert updated.quiet_hours_enabled is False
    assert updated.quiet_hours_start is None
    assert updated.quiet_hours_end is None
