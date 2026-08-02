from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.notification_policy import evaluate_notification
from app.core.timezone import now_in
from app.models import BotKey, BotPreference, ReminderEvent, User
from app.modules.habit import HabitModule
from app.modules.sport import SportModule
from app.modules.step import StepModule
from app.modules.supplement import SupplementModule
from app.services import (
    habit_service,
    preference_service,
    sport_service,
    step_service,
    supplement_service,
    user_service,
)
from tests.conftest import TELEGRAM_USER_ID

ALL_DAYS = "1,2,3,4,5,6,7"


async def _user(db_session: AsyncSession) -> int:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    return user.id


async def test_event_generated_when_preference_enabled(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await habit_service.create_habit(db_session, user_id, "Sabah sporu", 8, 30, ALL_DAYS)

    created = await HabitModule().generate_daily_events_for_all(db_session)

    assert created == 1


async def test_no_event_when_preference_disabled(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await habit_service.create_habit(db_session, user_id, "Sabah sporu", 8, 30, ALL_DAYS)
    await preference_service.toggle_preference(db_session, user_id, BotKey.HABIT, enabled=False)

    created = await HabitModule().generate_daily_events_for_all(db_session)

    assert created == 0


async def test_no_event_without_preference(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await habit_service.create_habit(db_session, user_id, "Sabah sporu", 8, 30, ALL_DAYS)
    await db_session.execute(delete(BotPreference))
    await db_session.commit()

    created = await HabitModule().generate_daily_events_for_all(db_session)

    assert created == 0


async def test_only_enabled_modules_generate(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    weekday = now_in().isoweekday()
    await habit_service.create_habit(db_session, user_id, "Sabah sporu", 8, 30, str(weekday))
    await sport_service.create_sport_plan(db_session, user_id, "Koşu", str(weekday), 18, 30)
    await step_service.get_or_create_settings(db_session, user_id)
    await supplement_service.create_supplement_plan(
        db_session, user_id, "D Vitamini", str(weekday), 9, 0
    )
    await preference_service.toggle_preference(db_session, user_id, BotKey.STEP, enabled=False)
    await preference_service.toggle_preference(
        db_session, user_id, BotKey.SUPPLEMENT, enabled=False
    )

    total = 0
    for module in (HabitModule(), SportModule(), StepModule(), SupplementModule()):
        total += await module.generate_daily_events_for_all(db_session)

    assert total == 2


async def test_no_events_after_disabling_between_days(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await habit_service.create_habit(db_session, user_id, "Sabah sporu", 8, 30, ALL_DAYS)
    module = HabitModule()
    day_one = now_in("UTC")

    first = await module.generate_daily_events_for_all(db_session, now_utc=day_one)

    await preference_service.toggle_preference(db_session, user_id, BotKey.HABIT, enabled=False)
    second = await module.generate_daily_events_for_all(
        db_session, now_utc=day_one + timedelta(days=1)
    )

    assert first == 1
    assert second == 0


async def test_notification_policy_still_suppresses_after_disable(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session)
    await habit_service.create_habit(db_session, user_id, "Sabah sporu", 8, 30, ALL_DAYS)
    await HabitModule().generate_daily_events_for_all(db_session)

    await preference_service.toggle_preference(db_session, user_id, BotKey.HABIT, enabled=False)

    user = await db_session.get(User, user_id)
    assert user is not None
    user.consent_given = True
    await db_session.commit()

    result = await db_session.execute(select(ReminderEvent).where(ReminderEvent.user_id == user_id))
    event = result.scalars().first()
    assert event is not None

    decision = await evaluate_notification(db_session, user, event, now_in("UTC"))

    assert decision["action"] == "suppress"
    assert decision["reason"] == "bot_disabled"


async def test_create_habit_enables_preference(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)

    await habit_service.create_habit(db_session, user_id, "Sabah sporu", 8, 30, ALL_DAYS)

    assert await preference_service.is_enabled(db_session, user_id, BotKey.HABIT) is True


async def test_generation_remains_idempotent_with_gating(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await habit_service.create_habit(db_session, user_id, "Sabah sporu", 8, 30, ALL_DAYS)
    module = HabitModule()

    first = await module.generate_daily_events_for_all(db_session)
    second = await module.generate_daily_events_for_all(db_session)

    assert first == 1
    assert second == 1
