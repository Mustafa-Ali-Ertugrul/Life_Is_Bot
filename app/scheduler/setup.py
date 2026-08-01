from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]

from app.core.config import settings
from app.core.logger import get_logger
from app.scheduler.engine import set_scheduler
from app.scheduler.jobs import habit_daily_job, reminder_tick, sport_daily_job

logger = get_logger("scheduler.setup")


def setup_scheduler() -> AsyncIOScheduler:
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
    scheduler.add_job(
        sport_daily_job,
        trigger="cron",
        hour=0,
        minute=6,
        id="sport_daily",
        replace_existing=True,
    )

    scheduler.start()
    set_scheduler(scheduler)
    logger.info("scheduler started", interval_seconds=settings.scheduler_interval_seconds)
    return scheduler


async def _debug_tick() -> None:
    from app.core.database import async_session_factory
    from app.services.user_service import count_active_users

    async with async_session_factory() as session:
        active_count = await count_active_users(session)
    logger.info("debug tick", active_users=active_count)


__all__ = ["setup_scheduler"]
