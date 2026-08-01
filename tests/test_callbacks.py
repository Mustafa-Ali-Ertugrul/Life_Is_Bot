from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BotKey, ReminderEvent, ReminderStatus, ResponseType
from app.services import reminder_service, response_service, user_service
from tests.conftest import TELEGRAM_USER_ID


async def test_save_response_stores_answer(db_session: AsyncSession) -> None:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    event = await reminder_service.create_event(
        db_session,
        user_id=user.id,
        bot_key=BotKey.STEP,
        scheduled_at=datetime(2026, 1, 1, 8, 0),
    )

    response = await response_service.save_response(
        db_session,
        reminder_event_id=event.id,
        user_id=user.id,
        bot_key=BotKey.STEP,
        response=ResponseType.DONE,
        source="test",
    )

    assert response.id is not None
    assert response.bot_key == BotKey.STEP.value
    assert response.response == ResponseType.DONE.value
    assert response.is_current is True


async def test_save_response_updates_event_status(db_session: AsyncSession) -> None:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    event = await reminder_service.create_event(
        db_session,
        user_id=user.id,
        bot_key=BotKey.STEP,
        scheduled_at=datetime(2026, 1, 1, 8, 0),
    )

    await response_service.save_response(
        db_session,
        reminder_event_id=event.id,
        user_id=user.id,
        bot_key=BotKey.STEP,
        response=ResponseType.DONE,
    )

    result = await db_session.execute(select(ReminderEvent).where(ReminderEvent.id == event.id))
    updated = result.scalar_one()
    assert updated.status == ReminderStatus.POSITIVE.value
