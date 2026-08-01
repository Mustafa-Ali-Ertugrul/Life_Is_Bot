from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from app.core.logger import get_logger

logger = get_logger("telegram.error_handler")

_USER_SAFE_MESSAGE = "Bir hata oluştu. Lütfen tekrar dene."


async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    error = context.error
    user_id: int | None = None
    update_type = "unknown"
    command: str | None = None

    if isinstance(update, Update):
        if update.effective_user is not None:
            user_id = update.effective_user.id
        if update.callback_query is not None:
            update_type = "callback_query"
        elif update.message is not None:
            update_type = "message"
            text = update.message.text
            if text is not None and text.startswith("/"):
                command = text.split(" ", 1)[0]

    logger.exception(
        "telegram handler error",
        error=str(error) if error is not None else None,
        user_id=user_id,
        update_type=update_type,
        command=command,
    )

    try:
        if isinstance(update, Update) and update.callback_query is not None:
            await update.callback_query.answer(_USER_SAFE_MESSAGE, show_alert=True)
        elif isinstance(update, Update) and update.effective_message is not None:
            await update.effective_message.reply_text(_USER_SAFE_MESSAGE)
    except Exception:
        logger.exception("failed to notify user about error", user_id=user_id)


def register_error_handler(application: Any) -> None:
    application.add_error_handler(handle_error)
