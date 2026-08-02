from collections.abc import Sequence
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.notification_policy import evaluate_notification
from app.core.timezone import now_in
from app.models import BotKey, ReminderEvent, User
from app.modules.base import EventGenerationContext, ReminderModule
from app.modules.habit import HabitModule
from app.modules.step import StepModule
from app.services import preference_service, reminder_service, user_service
from tests.conftest import TELEGRAM_USER_ID, TELEGRAM_USER_ID_2


async def _user(db_session: AsyncSession, telegram_id: str = TELEGRAM_USER_ID) -> int:
    user = await user_service.find_or_create_by_telegram_id(db_session, telegram_id)
    return user.id


async def _context(db_session: AsyncSession, user_id: int) -> EventGenerationContext:
    user = await db_session.get(User, user_id)
    assert user is not None
    return EventGenerationContext(user=user, now_utc=now_in("UTC"))


async def test_is_enabled_false_without_preference(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)

    assert await preference_service.is_enabled(db_session, user_id, BotKey.HABIT) is False


async def test_is_enabled_true_for_core_without_preference(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)

    assert await preference_service.is_enabled(db_session, user_id, BotKey.CORE) is True


async def test_is_enabled_true_when_enabled(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await preference_service.toggle_preference(db_session, user_id, BotKey.HABIT, enabled=True)

    assert await preference_service.is_enabled(db_session, user_id, BotKey.HABIT) is True


async def test_is_enabled_false_when_disabled(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await preference_service.toggle_preference(db_session, user_id, BotKey.HABIT, enabled=False)

    assert await preference_service.is_enabled(db_session, user_id, BotKey.HABIT) is False


async def test_is_enabled_isolated_per_bot_key(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await preference_service.toggle_preference(db_session, user_id, BotKey.STEP, enabled=True)

    assert await preference_service.is_enabled(db_session, user_id, BotKey.STEP) is True
    assert await preference_service.is_enabled(db_session, user_id, BotKey.HABIT) is False


async def test_is_enabled_isolated_per_user(db_session: AsyncSession) -> None:
    user_a = await _user(db_session)
    user_b = await _user(db_session, TELEGRAM_USER_ID_2)
    await preference_service.toggle_preference(db_session, user_a, BotKey.HABIT, enabled=True)

    assert await preference_service.is_enabled(db_session, user_a, BotKey.HABIT) is True
    assert await preference_service.is_enabled(db_session, user_b, BotKey.HABIT) is False


async def test_should_generate_true_when_enabled(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await preference_service.toggle_preference(db_session, user_id, BotKey.STEP, enabled=True)
    context = await _context(db_session, user_id)

    assert await StepModule().should_generate(db_session, context) is True


async def test_should_generate_false_when_disabled(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await preference_service.toggle_preference(db_session, user_id, BotKey.STEP, enabled=False)
    context = await _context(db_session, user_id)

    assert await StepModule().should_generate(db_session, context) is False


async def test_should_generate_false_without_preference(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    context = await _context(db_session, user_id)

    assert await StepModule().should_generate(db_session, context) is False


async def test_modules_use_their_own_bot_key(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await preference_service.toggle_preference(db_session, user_id, BotKey.STEP, enabled=True)
    context = await _context(db_session, user_id)

    assert await StepModule().should_generate(db_session, context) is True
    assert await HabitModule().should_generate(db_session, context) is False


async def test_should_generate_can_be_overridden(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    context = await _context(db_session, user_id)

    class AlwaysGenerateModule(ReminderModule):
        bot_key: ClassVar[BotKey] = BotKey.HABIT
        related_type: ClassVar[str] = "test_module"
        display_name: ClassVar[str] = "Test"

        async def generate_daily_events(
            self,
            session: AsyncSession,
            context: EventGenerationContext,
        ) -> Sequence[ReminderEvent]:
            return []

        def event_label(self, event: ReminderEvent) -> str | None:
            return None

        async def should_generate(
            self,
            session: AsyncSession,
            context: EventGenerationContext,
        ) -> bool:
            return True

    assert await AlwaysGenerateModule().should_generate(db_session, context) is True


async def test_is_enabled_matches_notification_policy(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    user = await db_session.get(User, user_id)
    assert user is not None
    user.consent_given = True
    user.notifications_enabled = True
    user.quiet_hours_enabled = False
    await db_session.commit()

    now = now_in("UTC")
    event = await reminder_service.create_event(
        db_session,
        user_id=user_id,
        bot_key=BotKey.HABIT,
        scheduled_at=now,
        related_type="habit",
        related_id=1,
    )

    decision = await evaluate_notification(db_session, user, event, now)
    assert decision["action"] == "suppress"
    assert decision["reason"] == "bot_disabled"
    assert await preference_service.is_enabled(db_session, user_id, BotKey.HABIT) is False

    await preference_service.toggle_preference(db_session, user_id, BotKey.HABIT, enabled=True)
    decision = await evaluate_notification(db_session, user, event, now)
    assert decision["action"] == "send_now"
    assert await preference_service.is_enabled(db_session, user_id, BotKey.HABIT) is True
