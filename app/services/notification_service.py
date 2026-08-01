from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone import now_in
from app.models import NotificationLog


async def log_notification(
    session: AsyncSession,
    user_id: int,
    message: str | None = None,
    reminder_event_id: int | None = None,
    channel: str = "telegram",
    status: str | None = None,
) -> NotificationLog:
    log = NotificationLog(
        reminder_event_id=reminder_event_id,
        user_id=user_id,
        channel=channel,
        message=message,
        status=status,
        sent_at=now_in("UTC"),
    )
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log
