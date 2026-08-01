from telegram import CallbackQuery, Update
from telegram.ext import ContextTypes

from app.core.database import async_session_factory
from app.models import BotKey
from app.services import preference_service, user_service
from app.telegram.keyboards import (
    CALLBACK_BOT_DETAIL,
    CALLBACK_BOT_LIST,
    CALLBACK_BOT_TOGGLE,
    CALLBACK_MAIN_MENU,
    bot_detail,
    bot_list,
    main_menu,
)
from app.telegram.messages import (
    BOT_ACTIVATED,
    BOT_DEACTIVATED,
    BOT_DETAIL,
    BOT_KEYS_TR,
    BOT_LIST_HEADER,
    BOT_LIST_ITEM,
    BOT_LIST_ITEM_ACTIVE,
    BOT_LIST_ITEM_INACTIVE,
    BOT_STATUS_ACTIVE,
    BOT_STATUS_INACTIVE,
    CORE_BOT_CANNOT_BE_DISABLED,
    HELP,
    REPORT_STUB,
    SETTINGS_STUB,
    WELCOME,
)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    assert query is not None
    assert query.data is not None
    assert update.effective_user is not None

    data = query.data
    user_data = context.user_data
    user_id: int | None = None
    if user_data is not None:
        user_id = user_data.get("user_id")

    if data == CALLBACK_MAIN_MENU:
        if user_id is None:
            user_id = await _ensure_user(context, update)
        await query.edit_message_text(WELCOME, reply_markup=main_menu())
        await query.answer()
        return

    if data == CALLBACK_BOT_LIST:
        if user_id is None:
            user_id = await _ensure_user(context, update)
        await _show_bot_list(query, user_id)
        return

    if data.startswith(f"{CALLBACK_BOT_DETAIL.split(':', 1)[0]}:"):
        if user_id is None:
            user_id = await _ensure_user(context, update)
        bot_key = BotKey(data.split(":", 1)[1])
        async with async_session_factory() as session:
            preference = await preference_service.get_or_create_preference(
                session, user_id, bot_key
            )
        can_toggle = bot_key is not BotKey.CORE
        status = BOT_STATUS_ACTIVE if preference.enabled else BOT_STATUS_INACTIVE
        text = BOT_DETAIL.format(name=BOT_KEYS_TR[bot_key], status=status)
        await query.edit_message_text(text, reply_markup=bot_detail(preference, can_toggle))
        await query.answer()
        return

    if data.startswith(f"{CALLBACK_BOT_TOGGLE.split(':', 1)[0]}:"):
        if user_id is None:
            user_id = await _ensure_user(context, update)
        bot_key = BotKey(data.split(":", 1)[1])
        async with async_session_factory() as session:
            existing = await preference_service.get_preference(session, user_id, bot_key)
            preference = (
                existing
                if existing is not None
                else await preference_service.get_or_create_preference(session, user_id, bot_key)
            )
            current_enabled = preference.enabled
            try:
                preference = await preference_service.toggle_preference(
                    session, user_id, bot_key, not current_enabled
                )
            except ValueError:
                await query.answer(CORE_BOT_CANNOT_BE_DISABLED, show_alert=True)
                return
        name = BOT_KEYS_TR[bot_key]
        status = BOT_STATUS_ACTIVE if preference.enabled else BOT_STATUS_INACTIVE
        text = (
            BOT_ACTIVATED.format(name=name)
            if preference.enabled
            else BOT_DEACTIVATED.format(name=name)
        )
        detail_text = BOT_DETAIL.format(name=name, status=status)
        await query.edit_message_text(
            detail_text, reply_markup=bot_detail(preference, bot_key is not BotKey.CORE)
        )
        await query.answer(text)
        return

    if data == "stub:settings":
        await query.edit_message_text(SETTINGS_STUB)
        await query.answer()
        return

    if data == "stub:reports":
        await query.edit_message_text(REPORT_STUB)
        await query.answer()
        return

    if data == "stub:help":
        await query.edit_message_text(HELP)
        await query.answer()
        return

    await query.answer("Geçersiz istek")


async def _show_bot_list(query: CallbackQuery, user_id: int) -> None:
    async with async_session_factory() as session:
        preferences = await preference_service.list_preferences(session, user_id)

    lines = [
        BOT_LIST_ITEM.format(
            status=BOT_LIST_ITEM_ACTIVE if p.enabled else BOT_LIST_ITEM_INACTIVE,
            label=BOT_KEYS_TR[p.bot_key_enum],
        )
        for p in preferences
    ]
    text = BOT_LIST_HEADER.format(BOT_LIST="\n".join(lines))
    await query.edit_message_text(text, reply_markup=bot_list(preferences))


async def _ensure_user(context: ContextTypes.DEFAULT_TYPE, update: Update) -> int:
    assert update.effective_user is not None
    telegram_user = update.effective_user
    async with async_session_factory() as session:
        user = await user_service.find_or_create_by_telegram_id(
            session,
            str(telegram_user.id),
            telegram_user.username,
            telegram_user.first_name,
        )
        if context.user_data is not None:
            context.user_data["user_id"] = user.id
        return user.id
