from app.core.config import settings
from app.core.database import async_session_factory
from app.core.logger import get_logger
from app.core.timezone import now_in
from app.services import habit_service, notification_service, reminder_service
from app.tgbot.notifier import send_reminder

logger = get_logger("scheduler.jobs")


async def reminder_tick() -> None:
    from app.scheduler.engine import get_bot

    bot = get_bot()
    if bot is None:
        logger.warning("reminder tick skipped, no bot instance")
        return

    async with async_session_factory() as session:
        due = await reminder_service.find_due_events(
            session, now_in(), limit=settings.scheduler_batch_size
        )
        for event in due:
            if await reminder_service.should_skip_notify(session, event):
                continue
            message_id = await send_reminder(bot, event)
            if message_id is None:
                logger.warning("reminder send failed, will retry", event_id=event.id)
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
                status="sent",
            )
    logger.info("reminder tick done", due_count=len(due))


async def habit_daily_job() -> None:
    async with async_session_factory() as session:
        created = await habit_service.generate_today_events_for_all(session)
    logger.info("habit daily job done", created_count=created)
