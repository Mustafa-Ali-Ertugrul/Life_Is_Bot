from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from telegram import Bot

from app.core.config import settings
from app.core.quiet_hours import is_within_quiet_hours
from app.core.timezone import get_user_timezone, now_in
from app.models import BotKey, NotificationLog, NotificationLogStatus, ReminderEvent, User
from app.services.event_labels import event_label
from app.tgbot.messages import (
    ABANDONED_MULTIPLE,
    ABANDONED_SINGLE,
    BOT_KEYS_TR,
    DIGEST_HEADER,
    DIGEST_ITEM,
)


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
    await session.flush()
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
            NotificationLog.retry_count < settings.notification_max_retries,
            or_(
                NotificationLog.next_retry_at.is_(None),
                NotificationLog.next_retry_at <= now,
            ),
        )
        .limit(settings.notification_retry_batch_size)
    )
    logs = (await session.execute(stmt)).scalars().all()

    processed = 0
    for log in logs:
        if log.reminder_event_id is None:
            log.status = NotificationLogStatus.ABANDONED.value
            log.next_retry_at = None
            processed += 1
            continue
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

    await session.flush()
    return processed


async def notify_abandoned(
    session: AsyncSession,
    bot: Bot,
    send_fn: Callable[[Bot, str, str], Awaitable[str | None]],
) -> int:
    """Abandoned bildirimler için kullanıcıya bir kez bilgi mesajı gönderir.

    Best-effort: gönderim fail olsa bile abandoned_notified işaretlenir (spam önleme).
    Kullanıcı başına tek mesaj. notification_logs'a yazılmaz (sonsuz döngü yok).
    """
    stmt = (
        select(NotificationLog)
        .where(
            NotificationLog.status == NotificationLogStatus.ABANDONED.value,
            NotificationLog.abandoned_notified.is_(False),
        )
        .limit(settings.notification_retry_batch_size)
    )
    logs = list((await session.execute(stmt)).scalars().all())
    if not logs:
        return 0

    by_user: dict[int, list[NotificationLog]] = {}
    for log in logs:
        by_user.setdefault(log.user_id, []).append(log)

    notified = 0
    for user_id, user_logs in by_user.items():
        user = await session.get(User, user_id, options=[selectinload(User.telegram_account)])
        chat_id = (
            user.telegram_account.telegram_user_id
            if user is not None and user.telegram_account is not None
            else None
        )
        text = await _format_abandoned(session, user_logs)
        sent = await send_fn(bot, chat_id, text) if chat_id is not None else None
        for log in user_logs:
            log.abandoned_notified = True
        if sent is not None:
            notified += 1

    await session.flush()
    return notified


async def _format_abandoned(session: AsyncSession, logs: list[NotificationLog]) -> str:
    names: list[str] = []
    for log in logs:
        if log.reminder_event_id is None:
            continue
        event = await session.get(ReminderEvent, log.reminder_event_id)
        if event is None:
            continue
        name = BOT_KEYS_TR[BotKey(event.bot_key)]
        if name not in names:
            names.append(name)
    if len(logs) == 1:
        return ABANDONED_SINGLE.format(bot_name=names[0] if names else "hatırlatma")
    bot_names = ", ".join(sorted(names)) if names else "çeşitli"
    return ABANDONED_MULTIPLE.format(count=len(logs), bot_names=bot_names)


async def send_digest(
    session: AsyncSession,
    bot: Bot,
    send_fn: Callable[[Bot, str, str], Awaitable[str | None]],
) -> int:
    """Digest'e kuyruklanan bildirimleri kullanıcı başına tek mesajda gönderir.

    Best-effort: gönderim fail olsa bile loglar failed'a geçer (retry job bireysel dener).
    Quiet hours aktifken kullanıcı atlanır, digest_pending kalır.
    """
    stmt = (
        select(NotificationLog)
        .where(NotificationLog.status == NotificationLogStatus.DIGEST_PENDING.value)
        .limit(settings.notification_retry_batch_size * 5)
    )
    logs = list((await session.execute(stmt)).scalars().all())
    if not logs:
        return 0

    by_user: dict[int, list[NotificationLog]] = {}
    for log in logs:
        by_user.setdefault(log.user_id, []).append(log)

    notified = 0
    now = now_in("UTC")
    for user_id, user_logs in by_user.items():
        user = await session.get(User, user_id, options=[selectinload(User.telegram_account)])
        if user is None or user.telegram_account is None:
            for log in user_logs:
                log.status = NotificationLogStatus.ABANDONED.value
                log.next_retry_at = None
            continue

        if (
            user.quiet_hours_enabled
            and user.quiet_hours_start is not None
            and user.quiet_hours_end is not None
        ):
            local_now = now.astimezone(get_user_timezone(user.timezone))
            if is_within_quiet_hours(local_now, user.quiet_hours_start, user.quiet_hours_end):
                continue

        text = await _format_digest(session, user_logs)
        if text is None:
            for log in user_logs:
                log.status = NotificationLogStatus.ABANDONED.value
                log.next_retry_at = None
            continue

        chat_id = user.telegram_account.telegram_user_id
        sent = await send_fn(bot, chat_id, text)
        for log in user_logs:
            if sent is not None:
                log.status = NotificationLogStatus.SENT.value
                log.sent_at = now
            else:
                log.status = NotificationLogStatus.FAILED.value
                log.next_retry_at = _compute_next_retry(0)
        if sent is not None:
            notified += 1

    await session.flush()
    return notified


async def _format_digest(session: AsyncSession, logs: list[NotificationLog]) -> str | None:
    items: list[str] = []
    for log in logs:
        if log.reminder_event_id is None:
            continue
        event = await session.get(ReminderEvent, log.reminder_event_id)
        if event is None:
            continue
        bot_name = BOT_KEYS_TR[BotKey(event.bot_key)]
        items.append(DIGEST_ITEM.format(bot_name=bot_name, label=event_label(event)))
    if not items:
        return None
    return DIGEST_HEADER + "\n".join(items)


__all__ = [
    "_compute_next_retry",
    "_format_abandoned",
    "_format_digest",
    "log_notification",
    "notify_abandoned",
    "retry_failed_notifications",
    "send_digest",
]
