from app.core.config import settings
from app.core.logger import get_logger, setup_logging
from app.scheduler.engine import stop_scheduler
from app.telegram.adapter import build_application

logger = get_logger("main")


def main() -> None:
    setup_logging(settings.log_level)
    application = build_application()
    try:
        logger.info("rutinbot starting", mode="polling")
        application.run_polling(allowed_updates=["message", "callback_query"])
    finally:
        stop_scheduler()
        logger.info("rutinbot stopped")


if __name__ == "__main__":
    main()
