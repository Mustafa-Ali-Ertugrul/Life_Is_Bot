import json

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from app.core.logger import get_logger
from app.models import BotKey, ReminderEvent
from app.tgbot.callback_parser import ReminderAction, format_reminder
from app.tgbot.messages import BOT_KEYS_TR

logger = get_logger("telegram.notifier")


def _event_label(event: ReminderEvent) -> str:
    if event.related_type == "habit":
        try:
            data = json.loads(event.interpretation_json or "{}")
        except ValueError:
            data = {}
        name = data.get("habit_name")
        if name:
            return str(name)
    return event.related_type or "hatırlatma"


def build_reminder_message(event: ReminderEvent) -> tuple[str, InlineKeyboardMarkup]:
    bot_name = BOT_KEYS_TR[BotKey(event.bot_key)]
    label = _event_label(event)
    text = f"{bot_name} hatırlatması: {label}"
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅", callback_data=format_reminder(event.id, ReminderAction.DONE)
                ),
                InlineKeyboardButton(
                    "❌", callback_data=format_reminder(event.id, ReminderAction.NOT_DONE)
                ),
            ],
            [
                InlineKeyboardButton(
                    "⏰ 10 dk",
                    callback_data=format_reminder(event.id, ReminderAction.SNOOZE, minutes=10),
                ),
                InlineKeyboardButton(
                    "⏭️", callback_data=format_reminder(event.id, ReminderAction.SKIP)
                ),
            ],
        ]
    )
    return text, keyboard


async def send_reminder(bot: Bot, event: ReminderEvent) -> str | None:
    account = event.user.telegram_account
    if account is None:
        logger.warning("reminder skipped, no telegram account", event_id=event.id)
        return None

    text, keyboard = build_reminder_message(event)
    try:
        message = await bot.send_message(
            chat_id=account.telegram_user_id,
            text=text,
            reply_markup=keyboard,
        )
        return str(message.message_id)
    except Exception:
        logger.exception("failed to send reminder", event_id=event.id)
        return None
