"""Step tracking Telegram UI handlers."""

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
from app.core.schedule import parse_days, parse_time, parse_user_days
from app.core.timezone import now_in
from app.models import StepSettings
from app.services import settings_service, step_service
from app.tgbot.callback_parser import UICallback
from app.tgbot.keyboards import step_menu, step_settings_detail
from app.tgbot.messages import (
    STEP_CANCELLED,
    STEP_DAYS_LINE,
    STEP_DAYS_PROMPT,
    STEP_DAYS_SAVED,
    STEP_FIRST_ACTIVATION,
    STEP_GOAL_LINE,
    STEP_GOAL_PROMPT,
    STEP_GOAL_SAVED,
    STEP_INVALID_DAYS,
    STEP_INVALID_GOAL,
    STEP_INVALID_STEPS,
    STEP_INVALID_TIME,
    STEP_LOG_PROMPT,
    STEP_LOG_SAVED,
    STEP_LOG_UPDATED,
    STEP_MENU_HEADER,
    STEP_REMINDER_LINE,
    STEP_SETTINGS_DAYS,
    STEP_SETTINGS_GOAL,
    STEP_SETTINGS_HEADER,
    STEP_SETTINGS_STATUS,
    STEP_SETTINGS_TIME,
    STEP_STATUS_ACTIVE,
    STEP_STATUS_INACTIVE,
    STEP_TIME_PROMPT,
    STEP_TIME_SAVED,
    STEP_TODAY_EMPTY,
    STEP_TODAY_PROGRESS,
    STEP_TOGGLED_OFF,
    STEP_TOGGLED_ON,
)

ASK_STEPS, ASK_GOAL, ASK_TIME, ASK_DAYS = range(4)

_ALL_DAYS = [1, 2, 3, 4, 5, 6, 7]

DAY_LABELS_TR: dict[int, str] = {
    1: "Pzt",
    2: "Sal",
    3: "Çar",
    4: "Per",
    5: "Cum",
    6: "Cmt",
    7: "Paz",
}


async def _ensure_user_id(context: ContextTypes.DEFAULT_TYPE, update: Update) -> int:
    user_data = context.user_data
    user_id = user_data.get("user_id") if user_data is not None else None
    if isinstance(user_id, int):
        return user_id
    from app.tgbot.callbacks import _ensure_user

    return await _ensure_user(context, update)


def _days_display(days_of_week: str) -> str:
    days = sorted(parse_days(days_of_week))
    if days == _ALL_DAYS:
        return "Her gün"
    return ", ".join(DAY_LABELS_TR.get(day, str(day)) for day in days)


def _time_display(hour: int, minute: int) -> str:
    return f"{hour:02d}:{minute:02d}"


def _pct(steps: int, goal: int) -> int:
    if goal <= 0:
        return 0
    return min(int(steps * 100 / goal), 999)


def _format_thousands(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _menu_text(settings: StepSettings, today_steps: int | None) -> str:
    lines = [STEP_MENU_HEADER, ""]
    if today_steps is not None:
        lines.append(
            STEP_TODAY_PROGRESS.format(
                steps=_format_thousands(today_steps),
                goal=_format_thousands(settings.daily_target),
                pct=_pct(today_steps, settings.daily_target),
            )
        )
    else:
        lines.append(STEP_TODAY_EMPTY)
    lines.append(STEP_GOAL_LINE.format(goal=_format_thousands(settings.daily_target)))
    lines.append(
        STEP_REMINDER_LINE.format(
            time=_time_display(settings.reminder_hour, settings.reminder_minute)
        )
    )
    lines.append(STEP_DAYS_LINE.format(days=_days_display(settings.days_of_week)))
    return "\n".join(lines)


def _settings_text(settings: StepSettings) -> str:
    status = STEP_STATUS_ACTIVE if settings.is_active else STEP_STATUS_INACTIVE
    return "\n".join(
        [
            STEP_SETTINGS_HEADER,
            "",
            STEP_SETTINGS_GOAL.format(goal=_format_thousands(settings.daily_target)),
            STEP_SETTINGS_TIME.format(
                time=_time_display(settings.reminder_hour, settings.reminder_minute)
            ),
            STEP_SETTINGS_DAYS.format(days=_days_display(settings.days_of_week)),
            STEP_SETTINGS_STATUS.format(status=status),
        ]
    )


async def _load_menu_data(session: Any, user_id: int) -> tuple[StepSettings, int | None]:
    settings = await step_service.get_or_create_settings(session, user_id)
    today_log = await step_service.get_today_steps(session, user_id)
    steps = today_log.steps if today_log is not None else None
    return settings, steps


async def step_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /adim command - show step tracking menu."""
    assert update.effective_message is not None
    user_id = await _ensure_user_id(context, update)

    async with async_session_factory() as session:
        existing = await step_service.get_settings(session, user_id)
        settings, steps = await _load_menu_data(session, user_id)

    if existing is None:
        await update.effective_message.reply_text(STEP_FIRST_ACTIVATION)
    await update.effective_message.reply_text(_menu_text(settings, steps), reply_markup=step_menu())


async def step_menu_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, parsed: UICallback
) -> None:
    """ui:step:menu - show step menu (edit message)."""
    assert update.callback_query is not None
    user_id = await _ensure_user_id(context, update)

    async with async_session_factory() as session:
        settings, steps = await _load_menu_data(session, user_id)

    await update.callback_query.edit_message_text(
        _menu_text(settings, steps), reply_markup=step_menu()
    )
    await update.callback_query.answer()


async def step_settings_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, parsed: UICallback
) -> None:
    """ui:step:settings - show settings detail."""
    assert update.callback_query is not None
    user_id = await _ensure_user_id(context, update)

    async with async_session_factory() as session:
        settings = await step_service.get_or_create_settings(session, user_id)

    await update.callback_query.edit_message_text(
        _settings_text(settings), reply_markup=step_settings_detail(settings)
    )
    await update.callback_query.answer()


async def step_toggle_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, parsed: UICallback
) -> None:
    """ui:step:toggle - toggle step bot active/inactive."""
    assert update.callback_query is not None
    user_id = await _ensure_user_id(context, update)

    async with async_session_factory() as session:
        settings = await step_service.get_or_create_settings(session, user_id)
        settings = await step_service.toggle_step_bot(session, user_id, not settings.is_active)

    toast = STEP_TOGGLED_ON if settings.is_active else STEP_TOGGLED_OFF
    await update.callback_query.edit_message_text(
        _settings_text(settings), reply_markup=step_settings_detail(settings)
    )
    await update.callback_query.answer(toast)


async def step_log_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """/adim_gir - ask for step count."""
    assert update.effective_message is not None
    await update.effective_message.reply_text(STEP_LOG_PROMPT)
    return ASK_STEPS


async def step_log_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ui:step:log - ask for step count (from button)."""
    assert update.callback_query is not None
    await update.callback_query.edit_message_text(STEP_LOG_PROMPT)
    await update.callback_query.answer()
    return ASK_STEPS


async def step_ask_steps(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validate and save step count."""
    assert update.effective_message is not None
    raw = (update.effective_message.text or "").strip().replace(".", "").replace(",", "")

    try:
        steps = int(raw)
    except ValueError:
        await update.effective_message.reply_text(STEP_INVALID_STEPS)
        return ASK_STEPS

    if not 0 <= steps <= 200000:
        await update.effective_message.reply_text(STEP_INVALID_STEPS)
        return ASK_STEPS

    user_id = await _ensure_user_id(context, update)

    async with async_session_factory() as session:
        settings = await step_service.get_or_create_settings(session, user_id)
        user = await settings_service.get_settings(session, user_id)
        local_date = now_in(user.timezone).date()
        existing = await step_service.get_steps_for_date(session, user_id, local_date)
        await step_service.log_steps(session, user_id, steps, local_date)

    if existing is not None:
        msg = STEP_LOG_UPDATED.format(
            steps=_format_thousands(steps),
            goal=_format_thousands(settings.daily_target),
            pct=_pct(steps, settings.daily_target),
        )
    else:
        msg = STEP_LOG_SAVED.format(
            steps=_format_thousands(steps),
            goal=_format_thousands(settings.daily_target),
            pct=_pct(steps, settings.daily_target),
        )
    await update.effective_message.reply_text(msg)
    return ConversationHandler.END


async def step_goal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ui:step:goal - ask for new daily target."""
    assert update.callback_query is not None
    await update.callback_query.edit_message_text(STEP_GOAL_PROMPT)
    await update.callback_query.answer()
    return ASK_GOAL


async def step_ask_goal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validate and save new daily target."""
    assert update.effective_message is not None
    raw = (update.effective_message.text or "").strip().replace(".", "").replace(",", "")

    try:
        goal = int(raw)
    except ValueError:
        await update.effective_message.reply_text(STEP_INVALID_GOAL)
        return ASK_GOAL

    if not 0 <= goal <= 100000:
        await update.effective_message.reply_text(STEP_INVALID_GOAL)
        return ASK_GOAL

    user_id = await _ensure_user_id(context, update)
    async with async_session_factory() as session:
        await step_service.update_daily_target(session, user_id, goal)

    await update.effective_message.reply_text(STEP_GOAL_SAVED.format(goal=_format_thousands(goal)))
    return ConversationHandler.END


async def step_time_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ui:step:time - ask for new reminder time."""
    assert update.callback_query is not None
    await update.callback_query.edit_message_text(STEP_TIME_PROMPT)
    await update.callback_query.answer()
    return ASK_TIME


async def step_ask_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validate and save new reminder time."""
    assert update.effective_message is not None
    raw = (update.effective_message.text or "").strip()

    try:
        hour, minute = parse_time(raw)
    except ValueError:
        await update.effective_message.reply_text(STEP_INVALID_TIME)
        return ASK_TIME

    user_id = await _ensure_user_id(context, update)
    async with async_session_factory() as session:
        await step_service.update_reminder_time(session, user_id, hour, minute)

    await update.effective_message.reply_text(
        STEP_TIME_SAVED.format(time=_time_display(hour, minute))
    )
    return ConversationHandler.END


async def step_days_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ui:step:days - ask for new days."""
    assert update.callback_query is not None
    await update.callback_query.edit_message_text(STEP_DAYS_PROMPT)
    await update.callback_query.answer()
    return ASK_DAYS


async def step_ask_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validate and save new days_of_week."""
    assert update.effective_message is not None
    raw = (update.effective_message.text or "").strip()

    try:
        days = parse_user_days(raw)
    except ValueError:
        await update.effective_message.reply_text(STEP_INVALID_DAYS)
        return ASK_DAYS

    user_id = await _ensure_user_id(context, update)
    async with async_session_factory() as session:
        settings = await step_service.update_days_of_week(session, user_id, days)

    await update.effective_message.reply_text(
        STEP_DAYS_SAVED.format(days=_days_display(settings.days_of_week))
    )
    return ConversationHandler.END


async def step_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """/iptal - cancel conversation."""
    assert update.effective_message is not None
    await update.effective_message.reply_text(STEP_CANCELLED)
    return ConversationHandler.END


def step_conversation() -> ConversationHandler[Any]:
    return ConversationHandler(
        entry_points=[
            CommandHandler("adim_gir", step_log_command),
            CallbackQueryHandler(step_log_callback, pattern="^ui:step:log$"),
            CallbackQueryHandler(step_goal_callback, pattern="^ui:step:goal$"),
            CallbackQueryHandler(step_time_callback, pattern="^ui:step:time$"),
            CallbackQueryHandler(step_days_callback, pattern="^ui:step:days$"),
        ],
        states={
            ASK_STEPS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, step_ask_steps),
            ],
            ASK_GOAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, step_ask_goal),
            ],
            ASK_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, step_ask_time),
            ],
            ASK_DAYS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, step_ask_days),
            ],
        },
        fallbacks=[CommandHandler("iptal", step_cancel)],
    )


__all__ = [
    "step_ask_days",
    "step_ask_goal",
    "step_ask_steps",
    "step_ask_time",
    "step_cancel",
    "step_conversation",
    "step_days_callback",
    "step_goal_callback",
    "step_log_callback",
    "step_log_command",
    "step_menu_callback",
    "step_menu_command",
    "step_settings_callback",
    "step_time_callback",
    "step_toggle_callback",
]
