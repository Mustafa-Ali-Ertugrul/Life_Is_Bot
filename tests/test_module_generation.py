from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone import now_in
from app.modules.habit import HabitModule
from app.modules.sport import SportModule
from app.modules.step import StepModule
from app.modules.supplement import SupplementModule
from app.services import (
    habit_service,
    sport_service,
    step_service,
    supplement_service,
    user_service,
)
from tests.conftest import TELEGRAM_USER_ID, TELEGRAM_USER_ID_2


async def _user(db_session: AsyncSession, telegram_id: str = TELEGRAM_USER_ID) -> int:
    user = await user_service.find_or_create_by_telegram_id(db_session, telegram_id)
    return user.id


async def _inactive_user(db_session: AsyncSession) -> int:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID_2)
    user.is_active = False
    await db_session.commit()
    return user.id


async def test_habit_module_generates_for_all_active_users(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    weekday = now_in().isoweekday()
    await habit_service.create_habit(db_session, user_id, "Sabah sporu", 8, 30, str(weekday))

    created = await HabitModule().generate_daily_events_for_all(db_session)

    assert created >= 1


async def test_sport_module_generates_for_all_active_users(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    weekday = now_in().isoweekday()
    await sport_service.create_sport_plan(db_session, user_id, "Koşu", str(weekday), 18, 30)

    created = await SportModule().generate_daily_events_for_all(db_session)

    assert created >= 1


async def test_supplement_module_generates_for_all_active_users(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session)
    weekday = now_in().isoweekday()
    await supplement_service.create_supplement_plan(
        db_session, user_id, "D Vitamini", str(weekday), 9, 0
    )

    created = await SupplementModule().generate_daily_events_for_all(db_session)

    assert created >= 1


async def test_step_module_generates_for_all_active_users(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await step_service.get_or_create_settings(db_session, user_id)

    created = await StepModule().generate_daily_events_for_all(db_session)

    assert created >= 1


async def test_generate_daily_events_for_all_skips_inactive_users(
    db_session: AsyncSession,
) -> None:
    active_user_id = await _user(db_session)
    inactive_user_id = await _inactive_user(db_session)
    weekday = now_in().isoweekday()
    await habit_service.create_habit(db_session, active_user_id, "Sabah sporu", 8, 30, str(weekday))
    await habit_service.create_habit(
        db_session, inactive_user_id, "Akşam sporu", 20, 0, str(weekday)
    )

    created = await HabitModule().generate_daily_events_for_all(db_session)

    assert created == 1


async def test_generate_daily_events_for_all_skips_users_without_plans(
    db_session: AsyncSession,
) -> None:
    await _user(db_session)

    created = await HabitModule().generate_daily_events_for_all(db_session)

    assert created == 0


async def test_generate_daily_events_for_all_is_idempotent(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    weekday = now_in().isoweekday()
    await habit_service.create_habit(db_session, user_id, "Sabah sporu", 8, 30, str(weekday))

    module = HabitModule()
    first = await module.generate_daily_events_for_all(db_session)
    second = await module.generate_daily_events_for_all(db_session)

    assert first == 1
    assert second == 1
