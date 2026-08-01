from typing import Any

from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
)

from app.core.config import settings
from app.core.logger import get_logger
from app.scheduler.engine import start_scheduler
from app.tgbot.callbacks import handle_callback
from app.tgbot.commands import cmd_ayarlar, cmd_botlar, cmd_rapor, cmd_start, cmd_yardim
from app.tgbot.error_handler import handle_error
from app.tgbot.messages import COMMANDS

logger = get_logger("telegram.adapter")

ApplicationT = Application[Any, Any, Any, Any, Any, Any]


async def _post_init(application: ApplicationT) -> None:
    start_scheduler()
    await application.bot.set_my_commands(COMMANDS)
    logger.info("telegram application initialized")


def build_application() -> ApplicationT:
    if not settings.bot_token:
        raise RuntimeError(
            "BOT_TOKEN boÅŸ. LÃ¼tfen .env dosyasÄ±na BotFather'dan aldÄ±ÄŸÄ±n token'Ä± yaz."
        )

    application = ApplicationBuilder().token(settings.bot_token).post_init(_post_init).build()

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("botlar", cmd_botlar))
    application.add_handler(CommandHandler("ayarlar", cmd_ayarlar))
    application.add_handler(CommandHandler("rapor", cmd_rapor))
    application.add_handler(CommandHandler("yardim", cmd_yardim))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_error_handler(handle_error)

    return application
