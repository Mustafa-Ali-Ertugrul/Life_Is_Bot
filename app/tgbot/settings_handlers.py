from typing import Any

from telegram import InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app.core.database import unit_of_work
from app.models import User
from app.services import settings_service
from app.tgbot.callback_parser import UICallback
from app.tgbot.keyboards import settings_menu
from app.tgbot.messages import (
    SETTINGS_ASK_QUIET_END,
    SETTINGS_ASK_QUIET_START,
    SETTINGS_ASK_TIMEZONE,
    SETTINGS_CANCELLED,
    SETTINGS_HEADER,
    SETTINGS_INVALID_TIME,
    SETTINGS_INVALID_TIMEZONE,
    SETTINGS_NOTIFICATIONS_OFF,
    SETTINGS_NOTIFICATIONS_OFF_MSG,
    SETTINGS_NOTIFICATIONS_ON,
    SETTINGS_NOTIFICATIONS_ON_MSG,
    SETTINGS_QUIET_HOURS_NONE,
    SETTINGS_QUIET_HOURS_OFF,
    SETTINGS_QUIET_HOURS_RANGE,
    SETTINGS_QUIET_HOURS_UPDATED,
    SETTINGS_TIMEZONE_UPDATED,
)

ASK_TZ, ASK_QH_START, ASK_QH_END = range(3)


def _get_user_id(context: ContextTypes.DEFAULT_TYPE) -> int | None:
    user_data = context.user_data
    if user_data is None:
        return None
    return user_data.get("user_id")


async def _ensure_user_id(context: ContextTypes.DEFAULT_TYPE, update: Update) -> int:
    user_id = _get_user_id(context)
    if user_id is None:
        from app.tgbot.callbacks import _ensure_user

        return await _ensure_user(context, update)
    return user_id


def _get_user_data(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any]:
    user_data = context.user_data
    if user_data is None:
        return {}
    return dict(user_data)


async def cmd_ayarlar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_message is not None
    user_id = await _ensure_user_id(context, update)
    text, keyboard = await _settings_payload(user_id)
    await update.effective_message.reply_text(text, reply_markup=keyboard)


async def show_settings_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, parsed: UICallback
) -> None:
    assert update.callback_query is not None
    user_id = await _ensure_user_id(context, update)
    text, keyboard = await _settings_payload(user_id)
    await update.callback_query.edit_message_text(text, reply_markup=keyboard)
    await update.callback_query.answer()


async def _settings_payload(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    async with unit_of_work() as session:
        user = await settings_service.get_settings(session, user_id)
    return _format_settings(user), settings_menu(user)


def _format_settings(user: User) -> str:
    quiet_hours = (
        SETTINGS_QUIET_HOURS_RANGE.format(
            start=user.quiet_hours_start or "-", end=user.quiet_hours_end or "-"
        )
        if user.quiet_hours_enabled
        else SETTINGS_QUIET_HOURS_NONE
    )
    notifications = (
        SETTINGS_NOTIFICATIONS_ON if user.notifications_enabled else SETTINGS_NOTIFICATIONS_OFF
    )
    return SETTINGS_HEADER.format(
        timezone=user.timezone,
        notifications=notifications,
        quiet_hours=quiet_hours,
    )


async def start_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.callback_query is not None
    await update.callback_query.edit_message_text(SETTINGS_ASK_TIMEZONE)
    await update.callback_query.answer()
    return ASK_TZ


async def tz_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    user_id = await _ensure_user_id(context, update)
    raw = (update.effective_message.text or "").strip()
    if not settings_service.is_valid_timezone(raw):
        await update.effective_message.reply_text(SETTINGS_INVALID_TIMEZONE)
        return ASK_TZ
    async with unit_of_work() as session:
        user = await settings_service.update_timezone(session, user_id, raw)
    await update.effective_message.reply_text(
        SETTINGS_TIMEZONE_UPDATED.format(timezone=user.timezone)
    )
    text, keyboard = await _settings_payload(user_id)
    await update.effective_message.reply_text(text, reply_markup=keyboard)
    return ConversationHandler.END


async def start_quiet_hours(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.callback_query is not None
    await update.callback_query.edit_message_text(SETTINGS_ASK_QUIET_START)
    await update.callback_query.answer()
    return ASK_QH_START


async def qh_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    raw = (update.effective_message.text or "").strip()
    if not settings_service.is_valid_hhmm(raw):
        await update.effective_message.reply_text(SETTINGS_INVALID_TIME)
        return ASK_QH_START
    context.user_data["quiet_hours_start"] = raw  # type: ignore[index]
    await update.effective_message.reply_text(SETTINGS_ASK_QUIET_END)
    return ASK_QH_END


async def qh_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    user_id = await _ensure_user_id(context, update)
    raw = (update.effective_message.text or "").strip()
    if not settings_service.is_valid_hhmm(raw):
        await update.effective_message.reply_text(SETTINGS_INVALID_TIME)
        return ASK_QH_END
    start = str(_get_user_data(context).get("quiet_hours_start", ""))
    async with unit_of_work() as session:
        user = await settings_service.set_quiet_hours(session, user_id, start, raw)
    await update.effective_message.reply_text(
        SETTINGS_QUIET_HOURS_UPDATED.format(
            start=user.quiet_hours_start or "-", end=user.quiet_hours_end or "-"
        )
    )
    text, keyboard = await _settings_payload(user_id)
    await update.effective_message.reply_text(text, reply_markup=keyboard)
    return ConversationHandler.END


async def toggle_notifications_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.callback_query is not None
    user_id = await _ensure_user_id(context, update)
    async with unit_of_work() as session:
        enabled = await settings_service.toggle_notifications(session, user_id)
    text, keyboard = await _settings_payload(user_id)
    await update.callback_query.edit_message_text(text, reply_markup=keyboard)
    await update.callback_query.answer(
        SETTINGS_NOTIFICATIONS_ON_MSG if enabled else SETTINGS_NOTIFICATIONS_OFF_MSG
    )


async def disable_quiet_hours_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.callback_query is not None
    user_id = await _ensure_user_id(context, update)
    async with unit_of_work() as session:
        await settings_service.clear_quiet_hours(session, user_id)
    text, keyboard = await _settings_payload(user_id)
    await update.callback_query.edit_message_text(text, reply_markup=keyboard)
    await update.callback_query.answer(SETTINGS_QUIET_HOURS_OFF)


async def cancel_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    await update.effective_message.reply_text(SETTINGS_CANCELLED)
    return ConversationHandler.END


def settings_conversation() -> ConversationHandler[Any]:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_timezone, pattern="^ui:settings:timezone$"),
            CallbackQueryHandler(start_quiet_hours, pattern="^ui:settings:quiet_hours$"),
        ],
        states={
            ASK_TZ: [MessageHandler(filters.TEXT & ~filters.COMMAND, tz_input)],
            ASK_QH_START: [MessageHandler(filters.TEXT & ~filters.COMMAND, qh_start)],
            ASK_QH_END: [MessageHandler(filters.TEXT & ~filters.COMMAND, qh_end)],
        },
        fallbacks=[CommandHandler("iptal", cancel_settings)],
    )


__all__ = [
    "cancel_settings",
    "cmd_ayarlar",
    "settings_conversation",
    "show_settings_menu",
]
