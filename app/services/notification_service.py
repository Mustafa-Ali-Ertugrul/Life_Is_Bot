from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Bot

from app.core.config import settings
from app.core.timezone import now_in
from app.models import NotificationLog, NotificationLogStatus, ReminderEvent


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


def _compute_next_retry(retry_count: int) -> datetime | None:
    if retry_count >= settings.notification_max_retries:
        return None
    idx = min(retry_count, len(settings.notification_retry_intervals) - 1)
    return now_in("UTC") + timedelta(seconds=settings.notification_retry_intervals[idx])


async def retry_failed_notifications(
    session: AsyncSession,
    bot: Bot,
    send_fn: Callable[[Bot, ReminderEvent], Awaitable[str | None]],
) -> int:
    now = now_in("UTC")
    stmt = (
        select(NotificationLog)
        .where(
            NotificationLog.status == NotificationLogStatus.FAILED.value,
            NotificationLog.next_retry_at <= now,
            NotificationLog.retry_count < settings.notification_max_retries,
        )
        .limit(settings.notification_retry_batch_size)
    )
    logs = (await session.execute(stmt)).scalars().all()

    processed = 0
    for log in logs:
        event = await session.get(ReminderEvent, log.reminder_event_id)
        if event is None:
            log.status = NotificationLogStatus.ABANDONED.value
            log.next_retry_at = None
            processed += 1
            continue
        message_id = await send_fn(bot, event)
        if message_id is not None:
            log.status = NotificationLogStatus.SENT.value
            log.next_retry_at = None
        else:
            log.retry_count += 1
            next_retry = _compute_next_retry(log.retry_count)
            if next_retry is None:
                log.status = NotificationLogStatus.ABANDONED.value
                log.next_retry_at = None
            else:
                log.next_retry_at = next_retry
        processed += 1

    await session.commit()
    return processed


__all__ = [
    "_compute_next_retry",
    "log_notification",
    "retry_failed_notifications",
]
