from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger("scheduler.engine")

_interval_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> AsyncIOScheduler:
    global _interval_scheduler
    if _interval_scheduler is not None and _interval_scheduler.running:
        return _interval_scheduler

    scheduler = AsyncIOScheduler(timezone=ZoneInfo(settings.timezone))
    scheduler.add_job(
        scheduler_tick,
        trigger="interval",
        seconds=settings.scheduler_interval_seconds,
        id="scheduler_tick",
        replace_existing=True,
        next_run_time=datetime.now(ZoneInfo(settings.timezone)) + timedelta(seconds=10),
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


async def scheduler_tick() -> None:
    from app.core.database import async_session_factory
    from app.services.user_service import count_active_users

    async with async_session_factory() as session:
        active_count = await count_active_users(session)
    logger.info("scheduler tick", active_users=active_count)
