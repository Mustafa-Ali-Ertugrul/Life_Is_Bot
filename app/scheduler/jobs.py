from dataclasses import asdict
from datetime import timedelta
from itertools import batched

from app.core.config import settings
from app.core.database import async_session_factory, unit_of_work
from app.core.logger import get_logger
from app.core.notification_policy import evaluate_notification
from app.core.timezone import now_in
from app.models import BotKey, NotificationLogStatus
from app.modules.base import EventGenerationContext
from app.modules.registry import get_modules
from app.services import (
    backup_service,
    notification_service,
    preference_service,
    purge_service,
    reminder_service,
    report_service,
    user_service,
)
from app.tgbot.messages import BOT_KEYS_TR
from app.tgbot.notifier import send_plain_text, send_reminder

logger = get_logger("scheduler.jobs")

DIGEST_BOT_KEYS: set[BotKey] = {
    BotKey.HABIT,
    BotKey.SPORT,
    BotKey.SUPPLEMENT,
    BotKey.STEP,
}

BATCH_SIZE = 100

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
                await notification_service.log_notification(
                    session,
                    user_id=event.user_id,
                    reminder_event_id=event.id,
                    message=f"reminder {event.id}",
                    channel="telegram",
                    status=NotificationLogStatus.DEFERRED_QUIET_HOURS.value,
                )
                await session.commit()
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
                await session.commit()
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
                await session.commit()
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
                await session.commit()
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
            await session.commit()
    logger.info("reminder tick done", due_count=len(due))


async def daily_events_job() -> None:
    total = 0
    now = now_in("UTC")
    modules = get_modules()
    bot_keys = [module.bot_key for module in modules]
    async with async_session_factory() as session:
        users = await user_service.list_active_users(session)
        for user_batch in batched(users, BATCH_SIZE):
            enabled_map = await preference_service.get_enabled_map(
                session, [user.id for user in user_batch], bot_keys
            )
            for user in user_batch:
                enabled_bots = frozenset(
                    bot_key
                    for (user_id, bot_key), enabled in enabled_map.items()
                    if user_id == user.id and enabled
                )
                context = EventGenerationContext(user=user, now_utc=now, enabled_bots=enabled_bots)
                for module in modules:
                    if not await module.should_generate(session, context):
                        continue
                    events = await module.generate_daily_events(session, context)
                    total += len(events)
                await session.commit()
    logger.info("daily events job done", created_count=total)


async def notification_retry_job() -> None:
    from app.scheduler.engine import get_bot

    bot = get_bot()
    if bot is None:
        logger.warning("notification retry skipped, no bot instance")
        return
    async with unit_of_work() as session:
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
    async with unit_of_work() as session:
        notified = await notification_service.notify_abandoned(session, bot, send_plain_text)
    if notified:
        logger.info("abandoned notification sent", user_count=notified)


async def notification_digest_job() -> None:
    from app.scheduler.engine import get_bot

    bot = get_bot()
    if bot is None:
        logger.warning("notification digest skipped, no bot instance")
        return
    async with unit_of_work() as session:
        notified = await notification_service.send_digest(session, bot, send_plain_text)
    if notified:
        logger.info("notification digest sent", user_count=notified)


async def daily_backup_job() -> None:
    """Nightly: create a SQLite backup and clean up backups older than retention."""
    if not settings.backup_enabled:
        return
    async with unit_of_work() as session:
        await backup_service.create_daily_backup(session)
    await backup_service.cleanup_old_backups()


async def monthly_report_job() -> None:
    """End of month: generate report for all users, save file, send via Telegram."""
    from app.scheduler.engine import get_bot

    if not settings.auto_monthly_report:
        return

    today = now_in(settings.timezone).date()
    if (today + timedelta(days=1)).month == today.month:
        return  # Son gün değil

    bot = get_bot()
    year, month = today.year, today.month
    async with unit_of_work() as session:
        users = await user_service.list_active_users_eager(session)
        for user in users:
            report = await report_service.generate_monthly_report(session, user.id, year, month)
            content = format_report_markdown(report)
            await backup_service.save_monthly_report_file(content, year, month, user.id)

            account = user.telegram_account
            if bot is not None and account is not None:
                sent = await send_plain_text(bot, account.telegram_user_id, content)
                if sent is None:
                    logger.warning("monthly report send failed", user_id=user.id)


async def monthly_purge_job() -> None:
    """End of month: purge old data after the monthly report, then VACUUM."""
    if not settings.purge_enabled:
        return

    today = now_in(settings.timezone).date()
    if (today + timedelta(days=1)).month == today.month:
        return  # Son gün değil

    size_before = purge_service.db_size()
    async with unit_of_work() as session:
        stats = await purge_service.purge_old_data(session, today)
    size_after = await purge_service.vacuum_database()

    logger.info(
        "monthly purge completed",
        **asdict(stats),
        size_before=size_before,
        size_after=size_after,
    )


def format_report_markdown(report: report_service.MonthlyReport) -> str:
    """Format MonthlyReport as plain text/markdown."""
    lines = [
        f"# Aylık Rapor — {report.year}-{report.month:02d}",
        "",
        f"Genel tamamlama: {report.completion_rate}% ({report.total_completed}/{report.total})",
        "",
    ]
    for stats in report.bot_stats:
        name = BOT_KEYS_TR[BotKey(stats.bot_key)]
        lines.append(
            f"- {name}: {stats.completion_rate}% "
            f"({stats.completed}/{stats.total}, kaçırılan {stats.missed}, "
            f"ertelenen {stats.snoozed}, bekleyen {stats.pending})"
        )
    lines += [
        "",
        f"Tamamlanan {report.total_completed} | Kaçırılan {report.total_missed} | "
        f"Bekleyen {report.total_pending}",
    ]
    return "\n".join(lines)
