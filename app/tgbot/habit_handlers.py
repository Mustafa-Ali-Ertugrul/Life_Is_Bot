from typing import Any

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app.core.database import async_session_factory
from app.services import habit_service
from app.tgbot.callback_parser import UICallback
from app.tgbot.keyboards import habit_confirm, habit_detail, habit_list
from app.tgbot.messages import (
    HABIT_ACTIVATED,
    HABIT_ASK_DAYS,
    HABIT_ASK_NAME,
    HABIT_ASK_TIME,
    HABIT_CANCELLED,
    HABIT_CONFIRM,
    HABIT_CREATED,
    HABIT_DAYS_TR,
    HABIT_DEACTIVATED,
    HABIT_DETAIL,
    HABIT_INVALID_DAYS,
    HABIT_INVALID_TIME,
    HABIT_LIST_EMPTY,
    HABIT_LIST_HEADER,
    HABIT_LIST_ITEM,
    HABIT_LIST_ITEM_ACTIVE,
    HABIT_LIST_ITEM_INACTIVE,
    HABIT_NOT_FOUND,
    HABIT_STATUS_ACTIVE,
    HABIT_STATUS_INACTIVE,
)

ASK_NAME, ASK_TIME, ASK_DAYS, CONFIRM = range(4)


def _days_label(days_of_week: str) -> str:
    labels: list[str] = []
    for day in sorted(habit_service.parse_days(days_of_week)):
        label = HABIT_DAYS_TR.get(day)
        if label is not None:
            labels.append(label)
    return ", ".join(labels) if labels else "-"


def _time_label(hour: int, minute: int) -> str:
    return f"{hour:02d}:{minute:02d}"


def _get_user_id(context: ContextTypes.DEFAULT_TYPE) -> int | None:
    user_data = context.user_data
    if user_data is None:
        return None
    return user_data.get("user_id")


def _get_habit_data(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any]:
    user_data = context.user_data
    if user_data is None:
        return {}
    return dict(user_data)


async def cmd_rutin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_message is not None
    user_id = _get_user_id(context)
    if user_id is None:
        from app.tgbot.callbacks import _ensure_user

        user_id = await _ensure_user(context, update)

    async with async_session_factory() as session:
        habits = await habit_service.list_habits(session, user_id)

    if not habits:
        await update.effective_message.reply_text(HABIT_LIST_EMPTY)
        return

    lines = [
        HABIT_LIST_ITEM.format(
            status=HABIT_LIST_ITEM_ACTIVE if h.is_active else HABIT_LIST_ITEM_INACTIVE,
            name=h.name,
        )
        for h in habits
    ]
    text = HABIT_LIST_HEADER.format(BOT_LIST="\n".join(lines))
    await update.effective_message.reply_text(text, reply_markup=habit_list(habits))


async def show_habit_list(
    update: Update, context: ContextTypes.DEFAULT_TYPE, parsed: UICallback
) -> None:
    assert update.callback_query is not None
    user_id = _get_user_id(context)
    if user_id is None:
        from app.tgbot.callbacks import _ensure_user

        user_id = await _ensure_user(context, update)

    async with async_session_factory() as session:
        habits = await habit_service.list_habits(session, user_id)

    if not habits:
        await update.callback_query.edit_message_text(HABIT_LIST_EMPTY)
        await update.callback_query.answer()
        return

    lines = [
        HABIT_LIST_ITEM.format(
            status=HABIT_LIST_ITEM_ACTIVE if h.is_active else HABIT_LIST_ITEM_INACTIVE,
            name=h.name,
        )
        for h in habits
    ]
    text = HABIT_LIST_HEADER.format(BOT_LIST="\n".join(lines))
    await update.callback_query.edit_message_text(text, reply_markup=habit_list(habits))
    await update.callback_query.answer()


async def show_habit_detail(
    update: Update, context: ContextTypes.DEFAULT_TYPE, parsed: UICallback
) -> None:
    assert update.callback_query is not None
    assert parsed.habit_id is not None
    user_id = _get_user_id(context)
    if user_id is None:
        from app.tgbot.callbacks import _ensure_user

        user_id = await _ensure_user(context, update)

    async with async_session_factory() as session:
        habit = await habit_service.get_habit(session, parsed.habit_id)
        if habit is None or habit.user_id != user_id:
            await update.callback_query.edit_message_text(HABIT_NOT_FOUND)
            await update.callback_query.answer()
            return

    status = HABIT_STATUS_ACTIVE if habit.is_active else HABIT_STATUS_INACTIVE
    text = HABIT_DETAIL.format(
        name=habit.name,
        time=_time_label(habit.target_hour, habit.target_minute),
        days=_days_label(habit.days_of_week),
        status=status,
    )
    await update.callback_query.edit_message_text(text, reply_markup=habit_detail(habit))
    await update.callback_query.answer()


async def toggle_habit(
    update: Update, context: ContextTypes.DEFAULT_TYPE, parsed: UICallback
) -> None:
    assert update.callback_query is not None
    assert parsed.habit_id is not None
    user_id = _get_user_id(context)
    if user_id is None:
        from app.tgbot.callbacks import _ensure_user

        user_id = await _ensure_user(context, update)

    async with async_session_factory() as session:
        habit = await habit_service.get_habit(session, parsed.habit_id)
        if habit is None or habit.user_id != user_id:
            await update.callback_query.edit_message_text(HABIT_NOT_FOUND)
            await update.callback_query.answer()
            return
        habit = await habit_service.toggle_habit(session, parsed.habit_id, not habit.is_active)
        assert habit is not None

    status = HABIT_STATUS_ACTIVE if habit.is_active else HABIT_STATUS_INACTIVE
    text = HABIT_DETAIL.format(
        name=habit.name,
        time=_time_label(habit.target_hour, habit.target_minute),
        days=_days_label(habit.days_of_week),
        status=status,
    )
    await update.callback_query.edit_message_text(text, reply_markup=habit_detail(habit))
    await update.callback_query.answer(HABIT_ACTIVATED if habit.is_active else HABIT_DEACTIVATED)


async def start_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    await update.effective_message.reply_text(HABIT_ASK_NAME)
    return ASK_NAME


async def start_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.callback_query is not None
    await update.callback_query.edit_message_text(HABIT_ASK_NAME)
    await update.callback_query.answer()
    return ASK_NAME


async def ask_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    context.user_data["habit_name"] = update.effective_message.text  # type: ignore[index]
    await update.effective_message.reply_text(HABIT_ASK_TIME)
    return ASK_TIME


async def ask_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    raw = (update.effective_message.text or "").strip()
    parts = raw.split(":")
    if len(parts) != 2:
        await update.effective_message.reply_text(HABIT_INVALID_TIME)
        return ASK_TIME
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        await update.effective_message.reply_text(HABIT_INVALID_TIME)
        return ASK_TIME
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        await update.effective_message.reply_text(HABIT_INVALID_TIME)
        return ASK_TIME
    context.user_data["habit_hour"] = hour  # type: ignore[index]
    context.user_data["habit_minute"] = minute  # type: ignore[index]
    await update.effective_message.reply_text(HABIT_ASK_DAYS)
    return ASK_DAYS


async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    raw = (update.effective_message.text or "").strip()
    days_of_week = "1,2,3,4,5,6,7"
    if raw:
        try:
            days = {int(part.strip()) for part in raw.split(",") if part.strip()}
        except ValueError:
            await update.effective_message.reply_text(HABIT_INVALID_DAYS)
            return ASK_DAYS
        if not days or not all(1 <= d <= 7 for d in days):
            await update.effective_message.reply_text(HABIT_INVALID_DAYS)
            return ASK_DAYS
        days_of_week = ",".join(str(d) for d in sorted(days))

    name = str(_get_habit_data(context).get("habit_name", ""))
    hour = int(_get_habit_data(context).get("habit_hour", 0))
    minute = int(_get_habit_data(context).get("habit_minute", 0))
    text = HABIT_CONFIRM.format(
        name=name,
        time=_time_label(hour, minute),
        days=_days_label(days_of_week),
    )
    await update.effective_message.reply_text(text, reply_markup=habit_confirm())
    return CONFIRM


async def confirm_yes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.callback_query is not None
    user_id = _get_user_id(context)
    if user_id is None:
        from app.tgbot.callbacks import _ensure_user

        user_id = await _ensure_user(context, update)

    data = _get_habit_data(context)
    name = str(data.get("habit_name", ""))
    hour = int(data.get("habit_hour", 0))
    minute = int(data.get("habit_minute", 0))
    days_of_week = str(data.get("habit_days", "1,2,3,4,5,6,7"))

    async with async_session_factory() as session:
        habit = await habit_service.create_habit(session, user_id, name, hour, minute, days_of_week)

    text = HABIT_CREATED.format(
        rutin=HABIT_DETAIL.format(
            name=habit.name,
            time=_time_label(habit.target_hour, habit.target_minute),
            days=_days_label(habit.days_of_week),
            status=HABIT_STATUS_ACTIVE,
        )
    )
    await update.callback_query.edit_message_text(text)
    await update.callback_query.answer()
    return ConversationHandler.END


async def confirm_no(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.callback_query is not None
    await update.callback_query.edit_message_text(HABIT_CANCELLED)
    await update.callback_query.answer()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    await update.effective_message.reply_text(HABIT_CANCELLED)
    return ConversationHandler.END


def habit_conversation() -> ConversationHandler[Any]:
    return ConversationHandler(
        entry_points=[
            CommandHandler("rutin_ekle", start_add),
            CallbackQueryHandler(start_add_callback, pattern="^ui:habit:new$"),
        ],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_time)],
            ASK_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_days)],
            ASK_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm)],
            CONFIRM: [
                CallbackQueryHandler(confirm_yes, pattern="^ui:habit:confirm$"),
                CallbackQueryHandler(confirm_no, pattern="^ui:habit:cancel$"),
            ],
        },
        fallbacks=[CommandHandler("iptal", cancel)],
    )


__all__ = [
    "cancel",
    "cmd_rutin",
    "habit_conversation",
    "show_habit_detail",
    "show_habit_list",
    "toggle_habit",
]
