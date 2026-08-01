from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from telegram import Bot

from app.core.config import settings
from app.core.logger import get_logger
from app.scheduler.jobs import habit_daily_job, reminder_tick

logger = get_logger("scheduler.engine")

_interval_scheduler: AsyncIOScheduler | None = None
_bot: Bot | None = None


def set_bot(bot: Bot) -> None:
    global _bot
    _bot = bot


def get_bot() -> Bot | None:
    return _bot


def start_scheduler() -> AsyncIOScheduler:
    global _interval_scheduler
    if _interval_scheduler is not None and _interval_scheduler.running:
        return _interval_scheduler

    scheduler = AsyncIOScheduler(timezone=ZoneInfo(settings.timezone))
    scheduler.add_job(
        reminder_tick,
        trigger="interval",
        seconds=settings.scheduler_interval_seconds,
        id="reminder_tick",
        replace_existing=True,
        next_run_time=datetime.now(ZoneInfo(settings.timezone)) + timedelta(seconds=10),
    )
    if settings.debug_scheduler:
        scheduler.add_job(
            _debug_tick,
            trigger="interval",
            seconds=settings.scheduler_interval_seconds,
            id="debug_tick",
            replace_existing=True,
        )
    scheduler.add_job(
        habit_daily_job,
        trigger="cron",
        hour=0,
        minute=5,
        id="habit_daily",
        replace_existing=True,
    )
    scheduler.start()
    _interval_scheduler = scheduler
    logger.info("scheduler started", interval_seconds=settings.scheduler_interval_seconds)
    return scheduler


def stop_scheduler() -> None:
    global _interval_scheduler
    if _interval_scheduler is not None:
        _interval_scheduler.shutdown(wait=False)
        _interval_scheduler = None
        logger.info("scheduler stopped")


async def _debug_tick() -> None:
    from app.core.database import async_session_factory
    from app.services.user_service import count_active_users

    async with async_session_factory() as session:
        active_count = await count_active_users(session)
    logger.info("debug tick", active_users=active_count)
