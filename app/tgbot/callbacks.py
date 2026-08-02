from datetime import timedelta

from telegram import CallbackQuery, Update
from telegram.ext import ContextTypes

from app.core.database import async_session_factory
from app.core.errors import InvalidStateError, NotFoundError, PermissionDeniedError
from app.core.logger import get_logger
from app.core.timezone import now_in
from app.models import BotKey, ResponseType
from app.services import preference_service, reminder_service, response_service, user_service
from app.tgbot.callback_parser import (
    HabitAction,
    ReminderAction,
    ReminderCallback,
    SportAction,
    StepAction,
    SupplementAction,
    UICallback,
    UICallbackKind,
    parse,
)
from app.tgbot.habit_handlers import show_habit_detail, show_habit_list, toggle_habit
from app.tgbot.keyboards import bot_detail, bot_list, main_menu
from app.tgbot.messages import (
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
    CONSENT_DENIED,
    CONSENT_GRANTED,
    CORE_BOT_CANNOT_BE_DISABLED,
    HELP,
    WELCOME,
)
from app.tgbot.report_handlers import show_report
from app.tgbot.settings_handlers import show_settings_menu
from app.tgbot.sport_handlers import (
    sport_detail_callback,
    sport_list_callback,
    sport_menu_callback,
    sport_toggle_callback,
)
from app.tgbot.step_handlers import (
    step_menu_callback,
    step_settings_callback,
    step_toggle_callback,
)
from app.tgbot.supplement_handlers import (
    supplement_detail_callback,
    supplement_list_callback,
    supplement_menu_callback,
    supplement_toggle_callback,
)

logger = get_logger("tgbot.callbacks")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    assert query is not None
    assert query.data is not None
    assert update.effective_user is not None

    parsed = parse(query.data)
    if isinstance(parsed, ReminderCallback):
        await _handle_reminder_callback(update, context, query, parsed)
        return
    if parsed is None:
        await query.answer("Geçersiz istek")
        return
    await _handle_ui_callback(update, context, query, parsed)


async def _handle_ui_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    query: CallbackQuery,
    parsed: UICallback,
) -> None:
    user_id: int | None = context.user_data.get("user_id") if context.user_data else None

    if parsed.kind is UICallbackKind.MAIN_MENU:
        if user_id is None:
            user_id = await _ensure_user(context, update)
        await query.edit_message_text(WELCOME, reply_markup=main_menu())
        await query.answer()
        return

    if parsed.kind is UICallbackKind.BOT_LIST:
        if user_id is None:
            user_id = await _ensure_user(context, update)
        await _show_bot_list(query, user_id)
        return

    if parsed.kind is UICallbackKind.BOT_DETAIL:
        if user_id is None:
            user_id = await _ensure_user(context, update)
        assert parsed.bot_key is not None
        await _show_bot_detail(query, user_id, parsed.bot_key)
        return

    if parsed.kind is UICallbackKind.BOT_TOGGLE:
        if user_id is None:
            user_id = await _ensure_user(context, update)
        assert parsed.bot_key is not None
        await _toggle_bot(query, user_id, parsed.bot_key)
        return

    if parsed.kind is UICallbackKind.HABIT:
        if parsed.habit_action is HabitAction.LIST:
            await show_habit_list(update, context, parsed)
            return
        if parsed.habit_action is HabitAction.DETAIL:
            await show_habit_detail(update, context, parsed)
            return
        if parsed.habit_action is HabitAction.TOGGLE:
            await toggle_habit(update, context, parsed)
            return
        await query.answer("Geçersiz istek")
        return

    if parsed.kind is UICallbackKind.SPORT:
        if parsed.sport_action is SportAction.MENU:
            await sport_menu_callback(update, context, parsed)
            return
        if parsed.sport_action is SportAction.LIST:
            await sport_list_callback(update, context, parsed)
            return
        if parsed.sport_action is SportAction.DETAIL:
            await sport_detail_callback(update, context, parsed)
            return
        if parsed.sport_action is SportAction.TOGGLE:
            await sport_toggle_callback(update, context, parsed)
            return
        await query.answer("Geçersiz istek")
        return

    if parsed.kind is UICallbackKind.SUPPLEMENT:
        if parsed.supplement_action is SupplementAction.MENU:
            await supplement_menu_callback(update, context, parsed)
            return
        if parsed.supplement_action is SupplementAction.LIST:
            await supplement_list_callback(update, context, parsed)
            return
        if parsed.supplement_action is SupplementAction.DETAIL:
            await supplement_detail_callback(update, context, parsed)
            return
        if parsed.supplement_action is SupplementAction.TOGGLE:
            await supplement_toggle_callback(update, context, parsed)
            return
        await query.answer("Geçersiz istek")
        return

    if parsed.kind is UICallbackKind.STEP:
        if parsed.step_action is StepAction.MENU:
            await step_menu_callback(update, context, parsed)
            return
        if parsed.step_action is StepAction.SETTINGS:
            await step_settings_callback(update, context, parsed)
            return
        if parsed.step_action is StepAction.TOGGLE:
            await step_toggle_callback(update, context, parsed)
            return
        await query.answer("Geçersiz istek")
        return

    if parsed.kind is UICallbackKind.CONSENT_YES:
        if user_id is None:
            user_id = await _ensure_user(context, update)
        async with async_session_factory() as session:
            await user_service.grant_consent(session, user_id)
        await query.edit_message_text(f"{CONSENT_GRANTED}\n\n{WELCOME}", reply_markup=main_menu())
        await query.answer()
        return

    if parsed.kind is UICallbackKind.CONSENT_NO:
        await query.edit_message_text(CONSENT_DENIED)
        await query.answer()
        return

    if parsed.kind is UICallbackKind.SETTINGS:
        await show_settings_menu(update, context, parsed)
        return

    if parsed.kind is UICallbackKind.REPORTS:
        await show_report(update, context, parsed)
        return

    if parsed.kind is UICallbackKind.HELP:
        await query.edit_message_text(HELP)
        await query.answer()
        return

    await query.answer("Geçersiz istek")


async def _handle_reminder_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    query: CallbackQuery,
    parsed: ReminderCallback,
) -> None:
    user_id: int | None = context.user_data.get("user_id") if context.user_data else None
    if user_id is None:
        user_id = await _ensure_user(context, update)

    async with async_session_factory() as session:
        event = await reminder_service.get_event(session, parsed.event_id)
        if event is None:
            await query.answer("Bildirim bulunamadı", show_alert=True)
            return
        if event.user_id != user_id:
            await query.answer("Bu bildirim size ait değil", show_alert=True)
            return

        bot_key = BotKey(event.bot_key)
        try:
            if parsed.action is ReminderAction.DONE:
                await response_service.save_response(
                    session, event.id, user_id, bot_key, ResponseType.DONE
                )
                await query.edit_message_text("Tamamlandı ✅")
            elif parsed.action is ReminderAction.NOT_DONE:
                await response_service.save_response(
                    session, event.id, user_id, bot_key, ResponseType.NOT_DONE
                )
                await query.edit_message_text("Kaydedildi ❌")
            elif parsed.action is ReminderAction.SKIP:
                await response_service.save_response(
                    session, event.id, user_id, bot_key, ResponseType.SKIPPED
                )
                await query.edit_message_text("Atlandı ⏭️")
            elif parsed.action is ReminderAction.SNOOZE:
                minutes = parsed.minutes or 10
                await response_service.save_response(
                    session, event.id, user_id, bot_key, ResponseType.SNOOZED
                )
                await reminder_service.reschedule_event(
                    session, event.id, now_in("UTC") + timedelta(minutes=minutes)
                )
                await query.edit_message_text(f"{minutes} dk sonra tekrar hatırlatacağım ⏰")
        except NotFoundError:
            logger.warning("reminder callback rejected, event missing", event_id=event.id)
            await query.answer("Hatırlatma bulunamadı", show_alert=True)
            return
        except PermissionDeniedError:
            logger.warning(
                "reminder callback rejected, permission denied", user_id=user_id, event_id=event.id
            )
            await query.answer("Bu işlem için yetkiniz yok", show_alert=True)
            return
        except InvalidStateError:
            logger.warning("reminder callback rejected, invalid state", event_id=event.id)
            await query.answer("Bu hatırlatma artık yanıtlanamaz", show_alert=True)
            return

    await query.answer()


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


async def _show_bot_detail(query: CallbackQuery, user_id: int, bot_key: BotKey) -> None:
    async with async_session_factory() as session:
        preference = await preference_service.get_or_create_preference(session, user_id, bot_key)
    can_toggle = bot_key is not BotKey.CORE
    status = BOT_STATUS_ACTIVE if preference.enabled else BOT_STATUS_INACTIVE
    text = BOT_DETAIL.format(name=BOT_KEYS_TR[bot_key], status=status)
    await query.edit_message_text(text, reply_markup=bot_detail(preference, can_toggle))
    await query.answer()


async def _toggle_bot(query: CallbackQuery, user_id: int, bot_key: BotKey) -> None:
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
        BOT_ACTIVATED.format(name=name) if preference.enabled else BOT_DEACTIVATED.format(name=name)
    )
    detail_text = BOT_DETAIL.format(name=name, status=status)
    await query.edit_message_text(
        detail_text, reply_markup=bot_detail(preference, bot_key is not BotKey.CORE)
    )
    await query.answer(text)


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
