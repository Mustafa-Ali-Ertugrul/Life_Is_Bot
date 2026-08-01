from telegram import InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.core.database import async_session_factory
from app.services import report_service
from app.services.report_service import DailyReport, WeeklyReport
from app.tgbot.callback_parser import ReportAction, UICallback
from app.tgbot.keyboards import report_menu
from app.tgbot.messages import (
    REPORT_BEST_DAY,
    REPORT_COMPLETED_HEADER,
    REPORT_COMPLIANCE,
    REPORT_DAILY_TITLE,
    REPORT_EMPTY,
    REPORT_ITEM_COMPLETED,
    REPORT_ITEM_MISSED,
    REPORT_MISSED_HEADER,
    REPORT_SUMMARY_LINES,
    REPORT_WEAKEST_DAY,
    REPORT_WEEKLY_TITLE,
    WEEKDAY_NAMES_TR,
)


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


async def cmd_rapor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_message is not None
    user_id = await _ensure_user_id(context, update)
    text, keyboard = await _daily_payload(user_id)
    await update.effective_message.reply_text(text, reply_markup=keyboard)


async def show_report(
    update: Update, context: ContextTypes.DEFAULT_TYPE, parsed: UICallback
) -> None:
    assert update.callback_query is not None
    user_id = await _ensure_user_id(context, update)
    if parsed.report_action is ReportAction.WEEKLY:
        text, keyboard = await _weekly_payload(user_id)
    else:
        text, keyboard = await _daily_payload(user_id)
    await update.callback_query.edit_message_text(text, reply_markup=keyboard)
    await update.callback_query.answer()


async def _daily_payload(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    async with async_session_factory() as session:
        data = await report_service.generate_daily_report(session, user_id)
    return _format_daily(data), report_menu()


async def _weekly_payload(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    async with async_session_factory() as session:
        data = await report_service.generate_weekly_report(session, user_id)
    return _format_weekly(data), report_menu()


def _format_daily(data: DailyReport) -> str:
    if data["total"] == 0:
        return f"{REPORT_DAILY_TITLE}\n\n{REPORT_EMPTY}"
    lines = [
        REPORT_DAILY_TITLE,
        "",
        REPORT_SUMMARY_LINES.format(
            total=data["total"],
            completed=data["completed"],
            missed=data["missed"],
            unanswered=data["unanswered"],
        ),
    ]
    if data["completed_items"]:
        lines.append("")
        lines.append(REPORT_COMPLETED_HEADER)
        lines.extend(REPORT_ITEM_COMPLETED.format(label=label) for label in data["completed_items"])
    if data["missed_items"]:
        lines.append("")
        lines.append(REPORT_MISSED_HEADER)
        lines.extend(REPORT_ITEM_MISSED.format(label=label) for label in data["missed_items"])
    return "\n".join(lines)


def _format_weekly(data: WeeklyReport) -> str:
    if data["total"] == 0:
        return f"{REPORT_WEEKLY_TITLE}\n\n{REPORT_EMPTY}"
    lines = [
        REPORT_WEEKLY_TITLE,
        "",
        REPORT_SUMMARY_LINES.format(
            total=data["total"],
            completed=data["completed"],
            missed=data["missed"],
            unanswered=data["unanswered"],
        ),
        "",
        REPORT_COMPLIANCE.format(rate=data["compliance_rate"]),
        REPORT_BEST_DAY.format(day=_weekday_name(data["best_day"])),
        REPORT_WEAKEST_DAY.format(day=_weekday_name(data["weakest_day"])),
    ]
    return "\n".join(lines)


def _weekday_name(weekday: int | None) -> str:
    if weekday is None:
        return "-"
    return WEEKDAY_NAMES_TR.get(weekday, "-")


__all__ = [
    "cmd_rapor",
    "show_report",
]
