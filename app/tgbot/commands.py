from telegram import Update
from telegram.ext import ContextTypes

from app.core.database import unit_of_work
from app.services import preference_service, user_service
from app.tgbot.keyboards import bot_list, consent_menu, main_menu
from app.tgbot.messages import (
    BOT_KEYS_TR,
    BOT_LIST_HEADER,
    BOT_LIST_ITEM,
    BOT_LIST_ITEM_ACTIVE,
    BOT_LIST_ITEM_INACTIVE,
    CONSENT_TEXT,
    HELP,
    WELCOME,
)
from app.tgbot.onboarding_handlers import onboarding_offer

MAIN_MENU_COMMANDS = {"start", "menu"}


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_user is not None
    assert update.effective_message is not None

    telegram_user = update.effective_user
    async with unit_of_work() as session:
        user = await user_service.find_or_create_by_telegram_id(
            session,
            str(telegram_user.id),
            telegram_user.username,
            telegram_user.first_name,
        )
        context.user_data["user_id"] = user.id  # type: ignore[index]

    if not user.consent_given:
        await update.effective_message.reply_text(CONSENT_TEXT, reply_markup=consent_menu())
        return

    if user.onboarding_completed_at is None and not user.onboarding_skipped:
        await onboarding_offer(update, context)
        return

    await update.effective_message.reply_text(WELCOME, reply_markup=main_menu())


async def cmd_botlar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_message is not None

    user_id = _get_user_id(context)
    if user_id is None:
        await update.effective_message.reply_text(WELCOME, reply_markup=main_menu())
        return

    async with unit_of_work() as session:
        preferences = await preference_service.list_preferences(session, user_id)

    lines = [
        BOT_LIST_ITEM.format(
            status=BOT_LIST_ITEM_ACTIVE if p.enabled else BOT_LIST_ITEM_INACTIVE,
            label=BOT_KEYS_TR[p.bot_key_enum],
        )
        for p in preferences
    ]
    await update.effective_message.reply_text(
        BOT_LIST_HEADER.format(BOT_LIST="\n".join(lines)), reply_markup=bot_list(preferences)
    )


async def cmd_yardim(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_message is not None
    await update.effective_message.reply_text(HELP)


def _get_user_id(context: ContextTypes.DEFAULT_TYPE) -> int | None:
    user_data = context.user_data
    if user_data is None:
        return None
    return user_data.get("user_id")
