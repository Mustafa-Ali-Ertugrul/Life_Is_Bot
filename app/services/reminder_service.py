from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone import now_in
from app.models import BotKey, ReminderEvent, ReminderStatus


async def create_event(
    session: AsyncSession,
    user_id: int,
    bot_key: BotKey,
    scheduled_at: datetime,
    related_type: str | None = None,
    related_id: int | None = None,
    interpretation_json: str = "{}",
) -> ReminderEvent:
    event = ReminderEvent(
        user_id=user_id,
        bot_key=bot_key.value,
        related_type=related_type,
        related_id=related_id,
        scheduled_at=scheduled_at,
        status=ReminderStatus.SCHEDULED.value,
        interpretation_json=interpretation_json,
        created_at=now_in(),
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event
