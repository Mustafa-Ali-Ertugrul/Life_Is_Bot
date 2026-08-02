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

from app.core.database import unit_of_work
from app.core.schedule import format_days, parse_days, parse_time, parse_user_days
from app.models import SportPlan
from app.services import sport_service
from app.tgbot.callback_parser import UICallback
from app.tgbot.keyboards import sport_confirm, sport_menu, sport_plan_detail, sport_plan_list
from app.tgbot.messages import (
    SPORT_ASK_DAYS,
    SPORT_ASK_TIME,
    SPORT_ASK_TYPE,
    SPORT_CANCELLED,
    SPORT_CONFIRM,
    SPORT_CREATED,
    SPORT_DAYS_TR,
    SPORT_DETAIL,
    SPORT_INVALID_DAYS,
    SPORT_INVALID_TIME,
    SPORT_INVALID_TYPE,
    SPORT_LIST_EMPTY,
    SPORT_LIST_HEADER,
    SPORT_LIST_ITEM,
    SPORT_LIST_ITEM_ACTIVE,
    SPORT_LIST_ITEM_INACTIVE,
    SPORT_MENU,
    SPORT_NOT_FOUND,
    SPORT_STATUS_ACTIVE,
    SPORT_STATUS_INACTIVE,
    SPORT_TOGGLED_OFF,
    SPORT_TOGGLED_ON,
)

ASK_TYPE, ASK_DAYS, ASK_TIME, CONFIRM = range(4)

DEFAULT_DAYS = [1, 2, 3, 4, 5]


def _days_label(days_of_week: str) -> str:
    labels: list[str] = []
    for day in sorted(parse_days(days_of_week)):
        label = SPORT_DAYS_TR.get(day)
        if label is not None:
            labels.append(label)
    return ", ".join(labels) if labels else "-"


def _time_label(hour: int, minute: int) -> str:
    return f"{hour:02d}:{minute:02d}"


def _list_text(plans: list[SportPlan]) -> str:
    lines = [
        SPORT_LIST_ITEM.format(
            status=SPORT_LIST_ITEM_ACTIVE if p.is_active else SPORT_LIST_ITEM_INACTIVE,
            sport_type=p.sport_type,
        )
        for p in plans
    ]
    return SPORT_LIST_HEADER.format(BOT_LIST="\n".join(lines))


def _detail_text(plan: SportPlan) -> str:
    status = SPORT_STATUS_ACTIVE if plan.is_active else SPORT_STATUS_INACTIVE
    return SPORT_DETAIL.format(
        sport_type=plan.sport_type,
        time=_time_label(plan.target_hour, plan.target_minute),
        days=_days_label(plan.days_of_week),
        status=status,
    )


def _get_user_id(context: ContextTypes.DEFAULT_TYPE) -> int | None:
    user_data = context.user_data
    if user_data is None:
        return None
    return user_data.get("user_id")


def _get_sport_data(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any]:
    user_data = context.user_data
    if user_data is None:
        return {}
    return dict(user_data)


async def sport_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_message is not None
    await update.effective_message.reply_text(SPORT_MENU, reply_markup=sport_menu())


async def sport_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_message is not None
    user_id = _get_user_id(context)
    if user_id is None:
        from app.tgbot.callbacks import _ensure_user

        user_id = await _ensure_user(context, update)

    async with unit_of_work() as session:
        plans = await sport_service.list_sport_plans(session, user_id)

    if not plans:
        await update.effective_message.reply_text(SPORT_LIST_EMPTY)
        return

    await update.effective_message.reply_text(
        _list_text(plans), reply_markup=sport_plan_list(plans)
    )


async def sport_menu_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, parsed: UICallback
) -> None:
    assert update.callback_query is not None
    await update.callback_query.edit_message_text(SPORT_MENU, reply_markup=sport_menu())
    await update.callback_query.answer()


async def sport_list_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, parsed: UICallback
) -> None:
    assert update.callback_query is not None
    user_id = _get_user_id(context)
    if user_id is None:
        from app.tgbot.callbacks import _ensure_user

        user_id = await _ensure_user(context, update)

    async with unit_of_work() as session:
        plans = await sport_service.list_sport_plans(session, user_id)

    if not plans:
        await update.callback_query.edit_message_text(SPORT_LIST_EMPTY)
        await update.callback_query.answer()
        return

    await update.callback_query.edit_message_text(
        _list_text(plans), reply_markup=sport_plan_list(plans)
    )
    await update.callback_query.answer()


async def sport_detail_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, parsed: UICallback
) -> None:
    assert update.callback_query is not None
    assert parsed.sport_plan_id is not None
    user_id = _get_user_id(context)
    if user_id is None:
        from app.tgbot.callbacks import _ensure_user

        user_id = await _ensure_user(context, update)

    async with unit_of_work() as session:
        plan = await sport_service.get_sport_plan(session, parsed.sport_plan_id)
        if plan is None or plan.user_id != user_id:
            await update.callback_query.edit_message_text(SPORT_NOT_FOUND)
            await update.callback_query.answer()
            return

    await update.callback_query.edit_message_text(
        _detail_text(plan), reply_markup=sport_plan_detail(plan)
    )
    await update.callback_query.answer()


async def sport_toggle_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, parsed: UICallback
) -> None:
    assert update.callback_query is not None
    assert parsed.sport_plan_id is not None
    user_id = _get_user_id(context)
    if user_id is None:
        from app.tgbot.callbacks import _ensure_user

        user_id = await _ensure_user(context, update)

    async with unit_of_work() as session:
        plan = await sport_service.get_sport_plan(session, parsed.sport_plan_id)
        if plan is None or plan.user_id != user_id:
            await update.callback_query.edit_message_text(SPORT_NOT_FOUND)
            await update.callback_query.answer()
            return
        plan = await sport_service.toggle_sport_plan(
            session, parsed.sport_plan_id, not plan.is_active
        )
        assert plan is not None

    await update.callback_query.edit_message_text(
        _detail_text(plan), reply_markup=sport_plan_detail(plan)
    )
    await update.callback_query.answer(SPORT_TOGGLED_ON if plan.is_active else SPORT_TOGGLED_OFF)


async def sport_add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    await update.effective_message.reply_text(SPORT_ASK_TYPE)
    return ASK_TYPE


async def sport_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.callback_query is not None
    await update.callback_query.edit_message_text(SPORT_ASK_TYPE)
    await update.callback_query.answer()
    return ASK_TYPE


async def sport_ask_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    sport_type = (update.effective_message.text or "").strip()
    if not sport_type:
        await update.effective_message.reply_text(SPORT_INVALID_TYPE)
        return ASK_TYPE
    context.user_data["sport_draft_type"] = sport_type  # type: ignore[index]
    await update.effective_message.reply_text(SPORT_ASK_DAYS)
    return ASK_DAYS


async def sport_ask_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    raw = (update.effective_message.text or "").strip()
    days = DEFAULT_DAYS
    if raw:
        try:
            days = parse_user_days(raw)
        except ValueError:
            await update.effective_message.reply_text(SPORT_INVALID_DAYS)
            return ASK_DAYS
    context.user_data["sport_draft_days"] = days  # type: ignore[index]
    await update.effective_message.reply_text(SPORT_ASK_TIME)
    return ASK_TIME


async def sport_ask_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    raw = (update.effective_message.text or "").strip()
    try:
        hour, minute = parse_time(raw)
    except ValueError:
        await update.effective_message.reply_text(SPORT_INVALID_TIME)
        return ASK_TIME
    context.user_data["sport_draft_hour"] = hour  # type: ignore[index]
    context.user_data["sport_draft_minute"] = minute  # type: ignore[index]
    await update.effective_message.reply_text(SPORT_CONFIRM, reply_markup=sport_confirm())
    return CONFIRM


async def sport_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.callback_query is not None
    user_id = _get_user_id(context)
    if user_id is None:
        from app.tgbot.callbacks import _ensure_user

        user_id = await _ensure_user(context, update)

    data = _get_sport_data(context)
    sport_type = str(data.get("sport_draft_type", ""))
    days = data.get("sport_draft_days", DEFAULT_DAYS)
    if not isinstance(days, list):
        days = DEFAULT_DAYS
    hour = int(data.get("sport_draft_hour", 0))
    minute = int(data.get("sport_draft_minute", 0))

    async with unit_of_work() as session:
        await sport_service.create_sport_plan(
            session, user_id, sport_type, format_days(days), hour, minute
        )

    await update.callback_query.edit_message_text(SPORT_CREATED)
    await update.callback_query.answer()
    return ConversationHandler.END


async def sport_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.callback_query is not None
    await update.callback_query.edit_message_text(SPORT_CANCELLED)
    await update.callback_query.answer()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    await update.effective_message.reply_text(SPORT_CANCELLED)
    return ConversationHandler.END


def sport_conversation() -> ConversationHandler[Any]:
    return ConversationHandler(
        entry_points=[
            CommandHandler("spor_ekle", sport_add_command),
            CallbackQueryHandler(sport_add_callback, pattern="^ui:sport:new$"),
        ],
        states={
            ASK_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, sport_ask_type)],
            ASK_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, sport_ask_days)],
            ASK_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, sport_ask_time)],
            CONFIRM: [
                CallbackQueryHandler(sport_confirm_callback, pattern="^ui:sport:confirm$"),
                CallbackQueryHandler(sport_cancel_callback, pattern="^ui:sport:cancel$"),
            ],
        },
        fallbacks=[CommandHandler("iptal", cancel)],
    )


__all__ = [
    "cancel",
    "sport_add_callback",
    "sport_add_command",
    "sport_ask_days",
    "sport_ask_time",
    "sport_ask_type",
    "sport_cancel_callback",
    "sport_confirm_callback",
    "sport_conversation",
    "sport_detail_callback",
    "sport_list_callback",
    "sport_list_command",
    "sport_menu_callback",
    "sport_menu_command",
    "sport_toggle_callback",
]
