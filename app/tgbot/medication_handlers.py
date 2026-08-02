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
from app.models import MedicationPlan
from app.services import medication_service, settings_service
from app.tgbot.callback_parser import UICallback
from app.tgbot.keyboards import (
    medication_confirm,
    medication_menu,
    medication_plan_detail,
    medication_plan_list,
)
from app.tgbot.messages import (
    MED_ASK_DAYS,
    MED_ASK_DOSE,
    MED_ASK_DURATION,
    MED_ASK_NAME,
    MED_ASK_NOTES,
    MED_ASK_TIME,
    MED_ASK_WITH_FOOD,
    MED_CANCELLED,
    MED_CONFIRM,
    MED_CREATED,
    MED_DAYS_TR,
    MED_DETAIL,
    MED_INVALID_DAYS,
    MED_INVALID_DURATION,
    MED_INVALID_NAME,
    MED_INVALID_TIME,
    MED_INVALID_WITH_FOOD,
    MED_LIST_EMPTY,
    MED_LIST_HEADER,
    MED_LIST_ITEM,
    MED_LIST_ITEM_ACTIVE,
    MED_LIST_ITEM_INACTIVE,
    MED_MENU,
    MED_NOT_FOUND,
    MED_STATUS_ACTIVE,
    MED_STATUS_INACTIVE,
    MED_TOGGLED_OFF,
    MED_TOGGLED_ON,
)

ASK_NAME, ASK_DOSE, ASK_WITH_FOOD, ASK_DAYS, ASK_TIME, ASK_DURATION, ASK_NOTES, CONFIRM = range(8)

DEFAULT_DAYS = [1, 2, 3, 4, 5, 6, 7]

_ALL_DAYS = [1, 2, 3, 4, 5, 6, 7]

_NO_INPUTS = {"yok", "-", "hayır"}


def _days_label(days: list[int]) -> str:
    labels: list[str] = []
    for day in sorted(days):
        label = MED_DAYS_TR.get(day)
        if label is not None:
            labels.append(label)
    return ", ".join(labels) if labels else "-"


def _days_display(days: list[int]) -> str:
    if sorted(days) == _ALL_DAYS:
        return "Her gün"
    return _days_label(days)


def _time_label(hour: int, minute: int) -> str:
    return f"{hour:02d}:{minute:02d}"


def _list_text(plans: list[MedicationPlan]) -> str:
    lines = [
        MED_LIST_ITEM.format(
            status=MED_LIST_ITEM_ACTIVE if p.is_active else MED_LIST_ITEM_INACTIVE,
            name=p.name,
        )
        for p in plans
    ]
    return MED_LIST_HEADER.format(BOT_LIST="\n".join(lines))


def _detail_text(plan: MedicationPlan) -> str:
    status = MED_STATUS_ACTIVE if plan.is_active else MED_STATUS_INACTIVE
    dose = plan.dose if plan.dose else "-"
    notes = plan.notes if plan.notes else "-"
    return MED_DETAIL.format(
        name=plan.name,
        dose=dose,
        with_food=with_food_label(plan.with_food),
        days=_days_display(sorted(parse_days(plan.days_of_week))),
        time=_time_label(plan.target_hour, plan.target_minute),
        duration=format_duration_range(_duration_days(plan), plan.start_date, plan.end_date),
        notes=notes,
        status=status,
    )


def _duration_days(plan: MedicationPlan) -> int:
    if plan.start_date is None or plan.end_date is None:
        return 0
    return (plan.end_date - plan.start_date).days + 1


def _summary_text(context: ContextTypes.DEFAULT_TYPE) -> str:
    data = _get_medication_data(context)
    name = str(data.get("med_draft_name", ""))
    dose = data.get("med_draft_dose")
    dose_text = str(dose) if dose else "-"
    with_food = with_food_label(str(data.get("med_draft_with_food", "any")))
    days = data.get("med_draft_days", DEFAULT_DAYS)
    if not isinstance(days, list):
        days = DEFAULT_DAYS
    hour = int(data.get("med_draft_hour", 0))
    minute = int(data.get("med_draft_minute", 0))
    duration_days = int(data.get("med_draft_duration_days", 0))
    start_date = data.get("med_draft_start_date")
    end_date = data.get("med_draft_end_date")
    notes = data.get("med_draft_notes")
    notes_text = str(notes) if notes else "-"
    duration_text = format_duration_range(duration_days, start_date, end_date)
    return (
        f"{MED_CONFIRM}\n\n"
        f"Ad: {name}\n"
        f"Doz: {dose_text}\n"
        f"Kullanım: {with_food}\n"
        f"Günler: {_days_display(days)}\n"
        f"Saat: {_time_label(hour, minute)}\n"
        f"Süre: {duration_text}\n"
        f"Not: {notes_text}"
    )


def _get_user_id(context: ContextTypes.DEFAULT_TYPE) -> int | None:
    user_data = context.user_data
    if user_data is None:
        return None
    return user_data.get("user_id")


def _get_medication_data(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any]:
    user_data = context.user_data
    if user_data is None:
        return {}
    return dict(user_data)


async def medication_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_message is not None
    await update.effective_message.reply_text(MED_MENU, reply_markup=medication_menu())


async def medication_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_message is not None
    user_id = _get_user_id(context)
    if user_id is None:
        from app.tgbot.callbacks import _ensure_user

        user_id = await _ensure_user(context, update)

    async with async_session_factory() as session:
        plans = await medication_service.list_medication_plans(session, user_id)

    if not plans:
        await update.effective_message.reply_text(MED_LIST_EMPTY)
        return

    await update.effective_message.reply_text(
        _list_text(plans), reply_markup=medication_plan_list(plans)
    )


async def medication_menu_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, parsed: UICallback
) -> None:
    assert update.callback_query is not None
    await update.callback_query.edit_message_text(MED_MENU, reply_markup=medication_menu())
    await update.callback_query.answer()


async def medication_list_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, parsed: UICallback
) -> None:
    assert update.callback_query is not None
    user_id = _get_user_id(context)
    if user_id is None:
        from app.tgbot.callbacks import _ensure_user

        user_id = await _ensure_user(context, update)

    async with async_session_factory() as session:
        plans = await medication_service.list_medication_plans(session, user_id)

    if not plans:
        await update.callback_query.edit_message_text(MED_LIST_EMPTY)
        await update.callback_query.answer()
        return

    await update.callback_query.edit_message_text(
        _list_text(plans), reply_markup=medication_plan_list(plans)
    )
    await update.callback_query.answer()


async def medication_detail_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, parsed: UICallback
) -> None:
    assert update.callback_query is not None
    assert parsed.medication_plan_id is not None
    user_id = _get_user_id(context)
    if user_id is None:
        from app.tgbot.callbacks import _ensure_user

        user_id = await _ensure_user(context, update)

    async with async_session_factory() as session:
        plan = await medication_service.get_medication_plan(session, parsed.medication_plan_id)
        if plan is None or plan.user_id != user_id:
            await update.callback_query.edit_message_text(MED_NOT_FOUND)
            await update.callback_query.answer()
            return

    await update.callback_query.edit_message_text(
        _detail_text(plan), reply_markup=medication_plan_detail(plan)
    )
    await update.callback_query.answer()


async def medication_toggle_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, parsed: UICallback
) -> None:
    assert update.callback_query is not None
    assert parsed.medication_plan_id is not None
    user_id = _get_user_id(context)
    if user_id is None:
        from app.tgbot.callbacks import _ensure_user

        user_id = await _ensure_user(context, update)

    async with async_session_factory() as session:
        plan = await medication_service.get_medication_plan(session, parsed.medication_plan_id)
        if plan is None or plan.user_id != user_id:
            await update.callback_query.edit_message_text(MED_NOT_FOUND)
            await update.callback_query.answer()
            return
        plan = await medication_service.toggle_medication_plan(
            session, parsed.medication_plan_id, not plan.is_active
        )
        assert plan is not None

    await update.callback_query.edit_message_text(
        _detail_text(plan), reply_markup=medication_plan_detail(plan)
    )
    await update.callback_query.answer(MED_TOGGLED_ON if plan.is_active else MED_TOGGLED_OFF)


async def medication_add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    await update.effective_message.reply_text(MED_ASK_NAME)
    return ASK_NAME


async def medication_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.callback_query is not None
    await update.callback_query.edit_message_text(MED_ASK_NAME)
    await update.callback_query.answer()
    return ASK_NAME


async def medication_ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    name = (update.effective_message.text or "").strip()
    if not name or len(name) > 120:
        await update.effective_message.reply_text(MED_INVALID_NAME)
        return ASK_NAME
    context.user_data["med_draft_name"] = name  # type: ignore[index]
    await update.effective_message.reply_text(MED_ASK_DOSE)
    return ASK_DOSE


async def medication_ask_dose(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    raw = (update.effective_message.text or "").strip()
    dose: str | None = None
    if raw and raw.lower() not in _NO_INPUTS:
        dose = raw
    context.user_data["med_draft_dose"] = dose  # type: ignore[index]
    await update.effective_message.reply_text(MED_ASK_WITH_FOOD)
    return ASK_WITH_FOOD


async def medication_ask_with_food(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    raw = (update.effective_message.text or "").strip()
    normalized = normalize_with_food_input(raw)
    if normalized is None:
        await update.effective_message.reply_text(MED_INVALID_WITH_FOOD)
        return ASK_WITH_FOOD
    context.user_data["med_draft_with_food"] = normalized  # type: ignore[index]
    await update.effective_message.reply_text(MED_ASK_DAYS)
    return ASK_DAYS


async def medication_ask_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    raw = (update.effective_message.text or "").strip()
    days = DEFAULT_DAYS
    if raw:
        try:
            days = parse_user_days(raw)
        except ValueError:
            await update.effective_message.reply_text(MED_INVALID_DAYS)
            return ASK_DAYS
    context.user_data["med_draft_days"] = days  # type: ignore[index]
    await update.effective_message.reply_text(MED_ASK_TIME)
    return ASK_TIME


async def medication_ask_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    raw = (update.effective_message.text or "").strip()
    try:
        hour, minute = parse_time(raw)
    except ValueError:
        await update.effective_message.reply_text(MED_INVALID_TIME)
        return ASK_TIME
    context.user_data["med_draft_hour"] = hour  # type: ignore[index]
    context.user_data["med_draft_minute"] = minute  # type: ignore[index]
    await update.effective_message.reply_text(MED_ASK_DURATION)
    return ASK_DURATION


async def medication_ask_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    raw = (update.effective_message.text or "").strip()
    try:
        duration_days = parse_duration_days(raw)
    except ValueError:
        await update.effective_message.reply_text(MED_INVALID_DURATION)
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

    context.user_data["med_draft_duration_days"] = duration_days  # type: ignore[index]
    context.user_data["med_draft_start_date"] = start_date  # type: ignore[index]
    context.user_data["med_draft_end_date"] = end_date  # type: ignore[index]

    await update.effective_message.reply_text(MED_ASK_NOTES)
    return ASK_NOTES


async def medication_ask_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    raw = (update.effective_message.text or "").strip()
    notes: str | None = None
    if raw and raw.lower() not in _NO_INPUTS:
        notes = raw
    context.user_data["med_draft_notes"] = notes  # type: ignore[index]

    await update.effective_message.reply_text(
        _summary_text(context), reply_markup=medication_confirm()
    )
    return CONFIRM


async def medication_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.callback_query is not None
    user_id = _get_user_id(context)
    if user_id is None:
        from app.tgbot.callbacks import _ensure_user

        user_id = await _ensure_user(context, update)

    data = _get_medication_data(context)
    name = str(data.get("med_draft_name", ""))
    dose = data.get("med_draft_dose")
    dose_value = str(dose) if dose else None
    with_food = str(data.get("med_draft_with_food", "any"))
    days = data.get("med_draft_days", DEFAULT_DAYS)
    if not isinstance(days, list):
        days = DEFAULT_DAYS
    hour = int(data.get("med_draft_hour", 0))
    minute = int(data.get("med_draft_minute", 0))
    start_date = data.get("med_draft_start_date")
    end_date = data.get("med_draft_end_date")
    notes = data.get("med_draft_notes")
    notes_value = str(notes) if notes else None

    async with async_session_factory() as session:
        await medication_service.create_medication_plan(
            session,
            user_id,
            name,
            target_hour=hour,
            target_minute=minute,
            days_of_week=format_days(days),
            dose=dose_value,
            with_food=with_food,
            start_date=start_date,
            end_date=end_date,
            notes=notes_value,
        )

    await update.callback_query.edit_message_text(MED_CREATED)
    await update.callback_query.answer()
    return ConversationHandler.END


async def medication_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.callback_query is not None
    await update.callback_query.edit_message_text(MED_CANCELLED)
    await update.callback_query.answer()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    await update.effective_message.reply_text(MED_CANCELLED)
    return ConversationHandler.END


def medication_conversation() -> ConversationHandler[Any]:
    return ConversationHandler(
        entry_points=[
            CommandHandler("ilac_ekle", medication_add_command),
            CallbackQueryHandler(medication_add_callback, pattern="^ui:med:new$"),
        ],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, medication_ask_name)],
            ASK_DOSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, medication_ask_dose)],
            ASK_WITH_FOOD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, medication_ask_with_food)
            ],
            ASK_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, medication_ask_days)],
            ASK_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, medication_ask_time)],
            ASK_DURATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, medication_ask_duration)
            ],
            ASK_NOTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, medication_ask_notes)],
            CONFIRM: [
                CallbackQueryHandler(medication_confirm_callback, pattern="^ui:med:confirm$"),
                CallbackQueryHandler(medication_cancel_callback, pattern="^ui:med:cancel$"),
            ],
        },
        fallbacks=[CommandHandler("iptal", cancel)],
    )


__all__ = [
    "cancel",
    "medication_add_callback",
    "medication_add_command",
    "medication_ask_days",
    "medication_ask_dose",
    "medication_ask_duration",
    "medication_ask_name",
    "medication_ask_notes",
    "medication_ask_time",
    "medication_ask_with_food",
    "medication_cancel_callback",
    "medication_confirm_callback",
    "medication_conversation",
    "medication_detail_callback",
    "medication_list_callback",
    "medication_list_command",
    "medication_menu_callback",
    "medication_menu_command",
    "medication_toggle_callback",
]
