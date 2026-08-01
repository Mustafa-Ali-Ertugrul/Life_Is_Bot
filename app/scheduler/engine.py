from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from telegram import Bot

from app.core.logger import get_logger

logger = get_logger("scheduler.engine")

_interval_scheduler: AsyncIOScheduler | None = None
_bot: Bot | None = None


def set_bot(bot: Bot) -> None:
    global _bot
    _bot = bot


def get_bot() -> Bot | None:
    return _bot


def set_scheduler(scheduler: AsyncIOScheduler) -> None:
    global _interval_scheduler
    _interval_scheduler = scheduler


def get_scheduler() -> AsyncIOScheduler | None:
    return _interval_scheduler


def stop_scheduler() -> None:
    global _interval_scheduler
    if _interval_scheduler is not None:
        _interval_scheduler.shutdown(wait=False)
        _interval_scheduler = None
        logger.info("scheduler stopped")


__all__ = [
    "get_bot",
    "get_scheduler",
    "set_bot",
    "set_scheduler",
    "stop_scheduler",
]
