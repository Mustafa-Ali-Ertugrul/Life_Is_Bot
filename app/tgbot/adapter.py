from typing import Any

from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
)

from app.core.config import settings
from app.core.logger import get_logger
from app.modules.registry import setup_default_modules
from app.scheduler.engine import set_bot
from app.scheduler.setup import setup_scheduler
from app.tgbot.callbacks import handle_callback
from app.tgbot.commands import cmd_botlar, cmd_start, cmd_yardim
from app.tgbot.error_handler import handle_error
from app.tgbot.habit_handlers import cmd_rutin, habit_conversation
from app.tgbot.messages import COMMANDS
from app.tgbot.report_handlers import cmd_rapor
from app.tgbot.settings_handlers import cmd_ayarlar, settings_conversation

logger = get_logger("telegram.adapter")

ApplicationT = Application[Any, Any, Any, Any, Any, Any]


async def _post_init(application: ApplicationT) -> None:
    set_bot(application.bot)
    setup_default_modules()
    setup_scheduler()
    await application.bot.set_my_commands(COMMANDS)
    logger.info("telegram application initialized")


def build_application() -> ApplicationT:
    if not settings.bot_token:
        raise RuntimeError(
            "BOT_TOKEN boş. Lütfen .env dosyasına BotFather'dan aldığın token'ı yaz."
        )

    application = ApplicationBuilder().token(settings.bot_token).post_init(_post_init).build()

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("botlar", cmd_botlar))
    application.add_handler(CommandHandler("ayarlar", cmd_ayarlar))
    application.add_handler(CommandHandler("rapor", cmd_rapor))
    application.add_handler(CommandHandler("yardim", cmd_yardim))
    application.add_handler(habit_conversation())
    application.add_handler(settings_conversation())
    application.add_handler(CommandHandler("rutin", cmd_rutin))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_error_handler(handle_error)

    return application
