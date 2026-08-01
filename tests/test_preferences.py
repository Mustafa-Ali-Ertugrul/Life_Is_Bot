import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BotKey
from app.services import preference_service, user_service
from tests.conftest import TELEGRAM_USER_ID


async def _create_user(db_session: AsyncSession) -> int:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    return user.id


async def test_toggle_enables_bot(db_session: AsyncSession) -> None:
    user_id = await _create_user(db_session)

    preference = await preference_service.toggle_preference(
        db_session, user_id, BotKey.SPORT, enabled=True
    )

    assert preference.enabled is True
    assert preference.bot_key == BotKey.SPORT.value


async def test_toggle_disables_bot(db_session: AsyncSession) -> None:
    user_id = await _create_user(db_session)
    await preference_service.toggle_preference(db_session, user_id, BotKey.SPORT, enabled=True)

    preference = await preference_service.toggle_preference(
        db_session, user_id, BotKey.SPORT, enabled=False
    )

    assert preference.enabled is False


async def test_core_bot_cannot_be_toggled(db_session: AsyncSession) -> None:
    user_id = await _create_user(db_session)

    with pytest.raises(ValueError, match="Ana bot kapatılamaz"):
        await preference_service.toggle_preference(db_session, user_id, BotKey.CORE, enabled=True)


async def test_list_preferences_contains_all_bots(db_session: AsyncSession) -> None:
    user_id = await _create_user(db_session)
    await preference_service.toggle_preference(db_session, user_id, BotKey.SPORT, enabled=True)

    preferences = await preference_service.list_preferences(db_session, user_id)

    assert len(preferences) == 1
    assert preferences[0].bot_key_enum is BotKey.SPORT


async def test_get_or_create_preference_unique(db_session: AsyncSession) -> None:
    user_id = await _create_user(db_session)
    first = await preference_service.get_or_create_preference(db_session, user_id, BotKey.HABIT)
    second = await preference_service.get_or_create_preference(db_session, user_id, BotKey.HABIT)

    assert first.id == second.id
