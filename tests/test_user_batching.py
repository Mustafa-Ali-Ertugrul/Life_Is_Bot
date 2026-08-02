from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone import now_in
from app.models import BotKey, User
from app.modules.base import EventGenerationContext
from app.modules.habit import HabitModule
from app.modules.step import StepModule
from app.services import preference_service, user_service
from tests.conftest import TELEGRAM_USER_ID, TELEGRAM_USER_ID_2


async def _user(db_session: AsyncSession, telegram_id: str = TELEGRAM_USER_ID) -> int:
    user = await user_service.find_or_create_by_telegram_id(db_session, telegram_id)
    return user.id


async def test_get_enabled_map_empty_without_preferences(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)

    enabled_map = await preference_service.get_enabled_map(db_session, [user_id])

    assert enabled_map == {}


async def test_get_enabled_map_includes_enabled_preference(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await preference_service.toggle_preference(db_session, user_id, BotKey.STEP, enabled=True)

    enabled_map = await preference_service.get_enabled_map(db_session, [user_id])

    assert enabled_map == {(user_id, BotKey.STEP.value): True}


async def test_get_enabled_map_includes_disabled_preference(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await preference_service.toggle_preference(db_session, user_id, BotKey.STEP, enabled=False)

    enabled_map = await preference_service.get_enabled_map(db_session, [user_id])

    assert enabled_map == {(user_id, BotKey.STEP.value): False}


async def test_get_enabled_map_isolates_users(db_session: AsyncSession) -> None:
    user_a = await _user(db_session)
    user_b = await _user(db_session, TELEGRAM_USER_ID_2)
    await preference_service.toggle_preference(db_session, user_a, BotKey.HABIT, enabled=True)

    enabled_map = await preference_service.get_enabled_map(db_session, [user_a, user_b])

    assert enabled_map == {(user_a, BotKey.HABIT.value): True}
    assert (user_b, BotKey.HABIT.value) not in enabled_map


async def test_get_enabled_map_filters_by_bot_keys(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await preference_service.toggle_preference(db_session, user_id, BotKey.HABIT, enabled=True)
    await preference_service.toggle_preference(db_session, user_id, BotKey.STEP, enabled=True)

    enabled_map = await preference_service.get_enabled_map(db_session, [user_id], [BotKey.STEP])

    assert enabled_map == {(user_id, BotKey.STEP.value): True}


async def test_get_enabled_map_missing_entries_absent(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await preference_service.toggle_preference(db_session, user_id, BotKey.HABIT, enabled=True)

    enabled_map = await preference_service.get_enabled_map(db_session, [user_id], [BotKey.STEP])

    assert enabled_map == {}


async def test_should_generate_uses_enabled_bots(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    user = await db_session.get(User, user_id)
    assert user is not None
    context = EventGenerationContext(
        user=user,
        now_utc=now_in("UTC"),
        enabled_bots=frozenset({BotKey.STEP.value}),
    )

    assert await StepModule().should_generate(db_session, context) is True
    assert await HabitModule().should_generate(db_session, context) is False


async def test_should_generate_empty_enabled_bots_means_none(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    user = await db_session.get(User, user_id)
    assert user is not None
    await preference_service.toggle_preference(db_session, user_id, BotKey.STEP, enabled=True)
    context = EventGenerationContext(
        user=user,
        now_utc=now_in("UTC"),
        enabled_bots=frozenset(),
    )

    assert await StepModule().should_generate(db_session, context) is False


async def test_should_generate_falls_back_to_is_enabled(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    user = await db_session.get(User, user_id)
    assert user is not None
    await preference_service.toggle_preference(db_session, user_id, BotKey.STEP, enabled=True)
    context = EventGenerationContext(user=user, now_utc=now_in("UTC"))

    assert await StepModule().should_generate(db_session, context) is True
    assert await HabitModule().should_generate(db_session, context) is False


async def test_list_active_users_excludes_inactive(db_session: AsyncSession) -> None:
    active_id = await _user(db_session)
    inactive_id = await _user(db_session, TELEGRAM_USER_ID_2)
    inactive = await db_session.get(User, inactive_id)
    assert inactive is not None
    inactive.is_active = False
    await db_session.commit()

    users = await user_service.list_active_users(db_session)

    assert [user.id for user in users] == [active_id]
