from datetime import timedelta
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
from app.core.schedule import format_days, parse_days, parse_time, parse_user_days
from app.core.supplement import (
    format_duration_range,
    normalize_with_food_input,
    parse_duration_days,
    with_food_label,
)
from app.core.timezone import now_in
from app.models import SupplementPlan
from app.services import settings_service, supplement_service
from app.tgbot.callback_parser import UICallback
from app.tgbot.keyboards import (
    supplement_confirm,
    supplement_menu,
    supplement_plan_detail,
    supplement_plan_list,
)
from app.tgbot.messages import (
    SUPPLEMENT_ASK_DAYS,
    SUPPLEMENT_ASK_DOSE,
    SUPPLEMENT_ASK_DURATION,
    SUPPLEMENT_ASK_NAME,
    SUPPLEMENT_ASK_TIME,
    SUPPLEMENT_ASK_WITH_FOOD,
    SUPPLEMENT_CANCELLED,
    SUPPLEMENT_CONFIRM,
    SUPPLEMENT_CREATED,
    SUPPLEMENT_DAYS_TR,
    SUPPLEMENT_DETAIL,
    SUPPLEMENT_INVALID_DAYS,
    SUPPLEMENT_INVALID_DURATION,
    SUPPLEMENT_INVALID_NAME,
    SUPPLEMENT_INVALID_TIME,
    SUPPLEMENT_INVALID_WITH_FOOD,
    SUPPLEMENT_LIST_EMPTY,
    SUPPLEMENT_LIST_HEADER,
    SUPPLEMENT_LIST_ITEM,
    SUPPLEMENT_LIST_ITEM_ACTIVE,
    SUPPLEMENT_LIST_ITEM_INACTIVE,
    SUPPLEMENT_MENU,
    SUPPLEMENT_NOT_FOUND,
    SUPPLEMENT_STATUS_ACTIVE,
    SUPPLEMENT_STATUS_INACTIVE,
    SUPPLEMENT_TOGGLED_OFF,
    SUPPLEMENT_TOGGLED_ON,
)

ASK_NAME, ASK_DOSE, ASK_WITH_FOOD, ASK_DAYS, ASK_TIME, ASK_DURATION, CONFIRM = range(7)

DEFAULT_DAYS = [1, 2, 3, 4, 5]

_ALL_DAYS = [1, 2, 3, 4, 5, 6, 7]

_NO_DOSE_INPUTS = {"yok", "-", "hayır"}


def _days_label(days: list[int]) -> str:
    labels: list[str] = []
    for day in sorted(days):
        label = SUPPLEMENT_DAYS_TR.get(day)
        if label is not None:
            labels.append(label)
    return ", ".join(labels) if labels else "-"


def _days_display(days: list[int]) -> str:
    if sorted(days) == _ALL_DAYS:
        return "Her gün"
    return _days_label(days)


def _time_label(hour: int, minute: int) -> str:
    return f"{hour:02d}:{minute:02d}"


def _list_text(plans: list[SupplementPlan]) -> str:
    lines = [
        SUPPLEMENT_LIST_ITEM.format(
            status=SUPPLEMENT_LIST_ITEM_ACTIVE if p.is_active else SUPPLEMENT_LIST_ITEM_INACTIVE,
            name=p.name,
        )
        for p in plans
    ]
    return SUPPLEMENT_LIST_HEADER.format(BOT_LIST="\n".join(lines))


def _detail_text(plan: SupplementPlan) -> str:
    status = SUPPLEMENT_STATUS_ACTIVE if plan.is_active else SUPPLEMENT_STATUS_INACTIVE
    dose = plan.dose if plan.dose else "-"
    return SUPPLEMENT_DETAIL.format(
        name=plan.name,
        dose=dose,
        with_food=with_food_label(plan.with_food),
        days=_days_display(sorted(parse_days(plan.days_of_week))),
        time=_time_label(plan.target_hour, plan.target_minute),
        duration=format_duration_range(_duration_days(plan), plan.start_date, plan.end_date),
        status=status,
    )


def _duration_days(plan: SupplementPlan) -> int:
    if plan.start_date is None or plan.end_date is None:
        return 0
    return (plan.end_date - plan.start_date).days + 1


def _summary_text(context: ContextTypes.DEFAULT_TYPE) -> str:
    data = _get_supplement_data(context)
    name = str(data.get("supp_draft_name", ""))
    dose = data.get("supp_draft_dose")
    dose_text = str(dose) if dose else "-"
    with_food = with_food_label(str(data.get("supp_draft_with_food", "any")))
    days = data.get("supp_draft_days", DEFAULT_DAYS)
    if not isinstance(days, list):
        days = DEFAULT_DAYS
    hour = int(data.get("supp_draft_hour", 0))
    minute = int(data.get("supp_draft_minute", 0))
    duration_days = int(data.get("supp_draft_duration_days", 0))
    start_date = data.get("supp_draft_start_date")
    end_date = data.get("supp_draft_end_date")
    duration_text = format_duration_range(duration_days, start_date, end_date)
    return (
        f"{SUPPLEMENT_CONFIRM}\n\n"
        f"Ad: {name}\n"
        f"Doz: {dose_text}\n"
        f"Kullanım: {with_food}\n"
        f"Günler: {_days_display(days)}\n"
        f"Saat: {_time_label(hour, minute)}\n"
        f"Süre: {duration_text}"
    )


def _get_user_id(context: ContextTypes.DEFAULT_TYPE) -> int | None:
    user_data = context.user_data
    if user_data is None:
        return None
    return user_data.get("user_id")


def _get_supplement_data(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any]:
    user_data = context.user_data
    if user_data is None:
        return {}
    return dict(user_data)


async def supplement_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_message is not None
    await update.effective_message.reply_text(SUPPLEMENT_MENU, reply_markup=supplement_menu())


async def supplement_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_message is not None
    user_id = _get_user_id(context)
    if user_id is None:
        from app.tgbot.callbacks import _ensure_user

        user_id = await _ensure_user(context, update)

    async with async_session_factory() as session:
        plans = await supplement_service.list_supplement_plans(session, user_id)

    if not plans:
        await update.effective_message.reply_text(SUPPLEMENT_LIST_EMPTY)
        return

    await update.effective_message.reply_text(
        _list_text(plans), reply_markup=supplement_plan_list(plans)
    )


async def supplement_menu_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, parsed: UICallback
) -> None:
    assert update.callback_query is not None
    await update.callback_query.edit_message_text(SUPPLEMENT_MENU, reply_markup=supplement_menu())
    await update.callback_query.answer()


async def supplement_list_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, parsed: UICallback
) -> None:
    assert update.callback_query is not None
    user_id = _get_user_id(context)
    if user_id is None:
        from app.tgbot.callbacks import _ensure_user

        user_id = await _ensure_user(context, update)

    async with async_session_factory() as session:
        plans = await supplement_service.list_supplement_plans(session, user_id)

    if not plans:
        await update.callback_query.edit_message_text(SUPPLEMENT_LIST_EMPTY)
        await update.callback_query.answer()
        return

    await update.callback_query.edit_message_text(
        _list_text(plans), reply_markup=supplement_plan_list(plans)
    )
    await update.callback_query.answer()


async def supplement_detail_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, parsed: UICallback
) -> None:
    assert update.callback_query is not None
    assert parsed.supplement_plan_id is not None
    user_id = _get_user_id(context)
    if user_id is None:
        from app.tgbot.callbacks import _ensure_user

        user_id = await _ensure_user(context, update)

    async with async_session_factory() as session:
        plan = await supplement_service.get_supplement_plan(session, parsed.supplement_plan_id)
        if plan is None or plan.user_id != user_id:
            await update.callback_query.edit_message_text(SUPPLEMENT_NOT_FOUND)
            await update.callback_query.answer()
            return

    await update.callback_query.edit_message_text(
        _detail_text(plan), reply_markup=supplement_plan_detail(plan)
    )
    await update.callback_query.answer()


async def supplement_toggle_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, parsed: UICallback
) -> None:
    assert update.callback_query is not None
    assert parsed.supplement_plan_id is not None
    user_id = _get_user_id(context)
    if user_id is None:
        from app.tgbot.callbacks import _ensure_user

        user_id = await _ensure_user(context, update)

    async with async_session_factory() as session:
        plan = await supplement_service.get_supplement_plan(session, parsed.supplement_plan_id)
        if plan is None or plan.user_id != user_id:
            await update.callback_query.edit_message_text(SUPPLEMENT_NOT_FOUND)
            await update.callback_query.answer()
            return
        plan = await supplement_service.toggle_supplement_plan(
            session, parsed.supplement_plan_id, not plan.is_active
        )
        assert plan is not None

    await update.callback_query.edit_message_text(
        _detail_text(plan), reply_markup=supplement_plan_detail(plan)
    )
    await update.callback_query.answer(
        SUPPLEMENT_TOGGLED_ON if plan.is_active else SUPPLEMENT_TOGGLED_OFF
    )


async def supplement_add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    await update.effective_message.reply_text(SUPPLEMENT_ASK_NAME)
    return ASK_NAME


async def supplement_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.callback_query is not None
    await update.callback_query.edit_message_text(SUPPLEMENT_ASK_NAME)
    await update.callback_query.answer()
    return ASK_NAME


async def supplement_ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    name = (update.effective_message.text or "").strip()
    if not name or len(name) > 120:
        await update.effective_message.reply_text(SUPPLEMENT_INVALID_NAME)
        return ASK_NAME
    context.user_data["supp_draft_name"] = name  # type: ignore[index]
    await update.effective_message.reply_text(SUPPLEMENT_ASK_DOSE)
    return ASK_DOSE


async def supplement_ask_dose(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    raw = (update.effective_message.text or "").strip()
    dose: str | None = None
    if raw and raw.lower() not in _NO_DOSE_INPUTS:
        dose = raw
    context.user_data["supp_draft_dose"] = dose  # type: ignore[index]
    await update.effective_message.reply_text(SUPPLEMENT_ASK_WITH_FOOD)
    return ASK_WITH_FOOD


async def supplement_ask_with_food(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    raw = (update.effective_message.text or "").strip()
    normalized = normalize_with_food_input(raw)
    if normalized is None:
        await update.effective_message.reply_text(SUPPLEMENT_INVALID_WITH_FOOD)
        return ASK_WITH_FOOD
    context.user_data["supp_draft_with_food"] = normalized  # type: ignore[index]
    await update.effective_message.reply_text(SUPPLEMENT_ASK_DAYS)
    return ASK_DAYS


async def supplement_ask_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    raw = (update.effective_message.text or "").strip()
    days = DEFAULT_DAYS
    if raw:
        try:
            days = parse_user_days(raw)
        except ValueError:
            await update.effective_message.reply_text(SUPPLEMENT_INVALID_DAYS)
            return ASK_DAYS
    context.user_data["supp_draft_days"] = days  # type: ignore[index]
    await update.effective_message.reply_text(SUPPLEMENT_ASK_TIME)
    return ASK_TIME


async def supplement_ask_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    raw = (update.effective_message.text or "").strip()
    try:
        hour, minute = parse_time(raw)
    except ValueError:
        await update.effective_message.reply_text(SUPPLEMENT_INVALID_TIME)
        return ASK_TIME
    context.user_data["supp_draft_hour"] = hour  # type: ignore[index]
    context.user_data["supp_draft_minute"] = minute  # type: ignore[index]
    await update.effective_message.reply_text(SUPPLEMENT_ASK_DURATION)
    return ASK_DURATION


async def supplement_ask_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    raw = (update.effective_message.text or "").strip()
    try:
        duration_days = parse_duration_days(raw)
    except ValueError:
        await update.effective_message.reply_text(SUPPLEMENT_INVALID_DURATION)
        return ASK_DURATION

    start_date = None
    end_date = None
    if duration_days > 0:
        user_id = _get_user_id(context)
        if user_id is None:
            from app.tgbot.callbacks import _ensure_user

            user_id = await _ensure_user(context, update)
        async with async_session_factory() as session:
            user = await settings_service.get_settings(session, user_id)
        start_date = now_in(user.timezone).date()
        end_date = start_date + timedelta(days=duration_days - 1)

    context.user_data["supp_draft_duration_days"] = duration_days  # type: ignore[index]
    context.user_data["supp_draft_start_date"] = start_date  # type: ignore[index]
    context.user_data["supp_draft_end_date"] = end_date  # type: ignore[index]

    await update.effective_message.reply_text(
        _summary_text(context), reply_markup=supplement_confirm()
    )
    return CONFIRM


async def supplement_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.callback_query is not None
    user_id = _get_user_id(context)
    if user_id is None:
        from app.tgbot.callbacks import _ensure_user

        user_id = await _ensure_user(context, update)

    data = _get_supplement_data(context)
    name = str(data.get("supp_draft_name", ""))
    dose = data.get("supp_draft_dose")
    dose_value = str(dose) if dose else None
    with_food = str(data.get("supp_draft_with_food", "any"))
    days = data.get("supp_draft_days", DEFAULT_DAYS)
    if not isinstance(days, list):
        days = DEFAULT_DAYS
    hour = int(data.get("supp_draft_hour", 0))
    minute = int(data.get("supp_draft_minute", 0))
    start_date = data.get("supp_draft_start_date")
    end_date = data.get("supp_draft_end_date")

    async with async_session_factory() as session:
        await supplement_service.create_supplement_plan(
            session,
            user_id,
            name,
            format_days(days),
            hour,
            minute,
            dose=dose_value,
            with_food=with_food,
            start_date=start_date,
            end_date=end_date,
        )

    await update.callback_query.edit_message_text(SUPPLEMENT_CREATED)
    await update.callback_query.answer()
    return ConversationHandler.END


async def supplement_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.callback_query is not None
    await update.callback_query.edit_message_text(SUPPLEMENT_CANCELLED)
    await update.callback_query.answer()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    await update.effective_message.reply_text(SUPPLEMENT_CANCELLED)
    return ConversationHandler.END


def supplement_conversation() -> ConversationHandler[Any]:
    return ConversationHandler(
        entry_points=[
            CommandHandler("supplement_ekle", supplement_add_command),
            CallbackQueryHandler(supplement_add_callback, pattern="^ui:supplement:new$"),
        ],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, supplement_ask_name)],
            ASK_DOSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, supplement_ask_dose)],
            ASK_WITH_FOOD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, supplement_ask_with_food)
            ],
            ASK_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, supplement_ask_days)],
            ASK_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, supplement_ask_time)],
            ASK_DURATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, supplement_ask_duration)
            ],
            CONFIRM: [
                CallbackQueryHandler(
                    supplement_confirm_callback, pattern="^ui:supplement:confirm$"
                ),
                CallbackQueryHandler(supplement_cancel_callback, pattern="^ui:supplement:cancel$"),
            ],
        },
        fallbacks=[CommandHandler("iptal", cancel)],
    )


__all__ = [
    "cancel",
    "supplement_add_callback",
    "supplement_add_command",
    "supplement_ask_days",
    "supplement_ask_dose",
    "supplement_ask_duration",
    "supplement_ask_name",
    "supplement_ask_time",
    "supplement_ask_with_food",
    "supplement_cancel_callback",
    "supplement_confirm_callback",
    "supplement_conversation",
    "supplement_detail_callback",
    "supplement_list_callback",
    "supplement_list_command",
    "supplement_menu_callback",
    "supplement_menu_command",
    "supplement_toggle_callback",
]
