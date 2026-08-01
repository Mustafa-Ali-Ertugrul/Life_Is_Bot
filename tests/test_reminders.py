from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BotKey, ReminderEvent, ReminderStatus
from app.services import reminder_service, user_service
from tests.conftest import TELEGRAM_USER_ID


async def test_create_event_schedules_reminder(db_session: AsyncSession) -> None:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)

    event = await reminder_service.create_event(
        db_session,
        user_id=user.id,
        bot_key=BotKey.MEDICATION,
        scheduled_at=datetime(2026, 1, 1, 8, 0, tzinfo=UTC),
        related_type="medication",
        interpretation_json='{"dosage": "1 tablet"}',
    )

    assert event.id is not None
    assert event.bot_key == BotKey.MEDICATION.value
    assert event.status == ReminderStatus.SCHEDULED.value


async def test_cancel_reminder_marks_cancelled(db_session: AsyncSession) -> None:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    event = await reminder_service.create_event(
        db_session,
        user_id=user.id,
        bot_key=BotKey.SUPPLEMENT,
        scheduled_at=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
    )

    from sqlalchemy import update

    await db_session.execute(
        update(ReminderEvent)
        .where(ReminderEvent.id == event.id)
        .values(status=ReminderStatus.CANCELLED.value)
    )
    await db_session.commit()

    result = await db_session.execute(select(ReminderEvent).where(ReminderEvent.id == event.id))
    cancelled = result.scalar_one()
    assert cancelled.status == ReminderStatus.CANCELLED.value


async def test_list_active_reminders_returns_pending(db_session: AsyncSession) -> None:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    await reminder_service.create_event(
        db_session,
        user_id=user.id,
        bot_key=BotKey.HABIT,
        scheduled_at=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
    )

    result = await db_session.execute(select(ReminderEvent).where(ReminderEvent.user_id == user.id))
    events = list(result.scalars().all())

    assert len(events) == 1
    assert events[0].bot_key == BotKey.HABIT.value
