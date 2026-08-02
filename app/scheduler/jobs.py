from app.core.config import settings
from app.core.database import async_session_factory
from app.core.logger import get_logger
from app.core.notification_policy import evaluate_notification
from app.core.timezone import now_in
from app.models import BotKey, NotificationLogStatus
from app.modules.registry import get_modules
from app.services import notification_service, reminder_service
from app.tgbot.notifier import send_plain_text, send_reminder

logger = get_logger("scheduler.jobs")

DIGEST_BOT_KEYS: set[BotKey] = {
    BotKey.HABIT,
    BotKey.SPORT,
    BotKey.SUPPLEMENT,
    BotKey.STEP,
}

_SUPPRESS_LOG_STATUSES: dict[str, str] = {
    "user_inactive": NotificationLogStatus.SUPPRESSED_USER_INACTIVE.value,
    "consent_missing": NotificationLogStatus.SUPPRESSED_CONSENT_MISSING.value,
    "notifications_disabled": NotificationLogStatus.SUPPRESSED_DISABLED.value,
    "bot_disabled": NotificationLogStatus.SUPPRESSED_BOT_DISABLED.value,
}


async def reminder_tick() -> None:
    from app.scheduler.engine import get_bot

    bot = get_bot()
    if bot is None:
        logger.warning("reminder tick skipped, no bot instance")
        return

    async with async_session_factory() as session:
        now = now_in("UTC")
        due = await reminder_service.find_due_events(
            session, now, limit=settings.scheduler_batch_size
        )
        for event in due:
            decision = await evaluate_notification(session, event.user, event, now)
            action = decision["action"]
            if action == "defer":
                event.notify_after = decision["defer_until"]
                await session.commit()
                await notification_service.log_notification(
                    session,
                    user_id=event.user_id,
                    reminder_event_id=event.id,
                    message=f"reminder {event.id}",
                    channel="telegram",
                    status=NotificationLogStatus.DEFERRED_QUIET_HOURS.value,
                )
                continue
            if action == "suppress":
                if decision["reason"] in ("already_responded", "not_scheduled", "already_notified"):
                    continue
                suppressed = await reminder_service.mark_suppressed(session, event.id)
                if not suppressed:
                    logger.warning("reminder already handled", event_id=event.id)
                    continue
                await notification_service.log_notification(
                    session,
                    user_id=event.user_id,
                    reminder_event_id=event.id,
                    message=f"reminder {event.id}",
                    channel="telegram",
                    status=_SUPPRESS_LOG_STATUSES[decision["reason"]],
                )
                continue
            if BotKey(event.bot_key) in DIGEST_BOT_KEYS:
                notified = await reminder_service.mark_notified(session, event.id)
                if not notified:
                    logger.warning("reminder already handled", event_id=event.id)
                    continue
                await notification_service.log_notification(
                    session,
                    user_id=event.user_id,
                    reminder_event_id=event.id,
                    message=f"reminder {event.id}",
                    channel="telegram",
                    status=NotificationLogStatus.DIGEST_PENDING.value,
                )
                continue
            message_id = await send_reminder(bot, event)
            if message_id is None:
                logger.warning("reminder send failed, will retry", event_id=event.id)
                await notification_service.log_notification(
                    session,
                    user_id=event.user_id,
                    reminder_event_id=event.id,
                    message=f"reminder {event.id}",
                    channel="telegram",
                    status=NotificationLogStatus.FAILED.value,
                )
                continue
            notified = await reminder_service.mark_notified(session, event.id)
            if not notified:
                logger.warning("reminder already handled", event_id=event.id)
                continue
            await notification_service.log_notification(
                session,
                user_id=event.user_id,
                reminder_event_id=event.id,
                message=f"reminder {event.id}",
                channel="telegram",
                status=NotificationLogStatus.SENT.value,
            )
    logger.info("reminder tick done", due_count=len(due))


async def daily_events_job() -> None:
    total = 0
    now = now_in("UTC")
    async with async_session_factory() as session:
        for module in get_modules():
            created = await module.generate_daily_events_for_all(session, now_utc=now)
            total += created
    logger.info("daily events job done", created_count=total)


async def notification_retry_job() -> None:
    from app.scheduler.engine import get_bot

    bot = get_bot()
    if bot is None:
        logger.warning("notification retry skipped, no bot instance")
        return
    async with async_session_factory() as session:
        processed = await notification_service.retry_failed_notifications(
            session, bot, send_reminder
        )
    if processed:
        logger.info("notification retry done", count=processed)


async def abandoned_notification_job() -> None:
    from app.scheduler.engine import get_bot

    bot = get_bot()
    if bot is None:
        logger.warning("abandoned notification skipped, no bot instance")
        return
    async with async_session_factory() as session:
        notified = await notification_service.notify_abandoned(session, bot, send_plain_text)
    if notified:
        logger.info("abandoned notification sent", user_count=notified)


async def notification_digest_job() -> None:
    from app.scheduler.engine import get_bot

    bot = get_bot()
    if bot is None:
        logger.warning("notification digest skipped, no bot instance")
        return
    async with async_session_factory() as session:
        notified = await notification_service.send_digest(session, bot, send_plain_text)
    if notified:
        logger.info("notification digest sent", user_count=notified)
