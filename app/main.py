import asyncio

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.logger import get_logger, setup_logging
from app.core.runtime import check_database, validate_startup_env
from app.scheduler.engine import stop_scheduler
from app.tgbot.adapter import build_application

logger = get_logger("main")


def main() -> None:
    setup_logging(settings.log_level)
    validate_startup_env()
    asyncio.run(check_database(async_session_factory))

    application = build_application()
    try:
        logger.info("life_is_bot starting", mode="polling", timezone=settings.timezone)
        application.run_polling(allowed_updates=["message", "callback_query"])
    except Exception:
        logger.exception("life_is_bot fatal error")
        raise
    finally:
        stop_scheduler()
        logger.info("life_is_bot stopped")


if __name__ == "__main__":
    main()
