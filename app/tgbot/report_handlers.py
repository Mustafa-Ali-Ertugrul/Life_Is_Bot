from telegram import InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.core.database import unit_of_work
from app.core.timezone import now_in
from app.models import BotKey
from app.services import report_service, settings_service
from app.services.report_service import DailyReport, MonthlyReport, WeeklyReport, YearlyReport
from app.tgbot.callback_parser import ReportAction, UICallback
from app.tgbot.keyboards import monthly_report_nav, report_menu
from app.tgbot.messages import (
    BOT_ICONS,
    BOT_KEYS_TR,
    DAILY_REPORT_STEP_LINE,
    MONTHLY_REPORT_BOT_LINE,
    MONTHLY_REPORT_EMPTY,
    MONTHLY_REPORT_HEADER,
    MONTHLY_REPORT_INVALID_ARG,
    MONTHLY_REPORT_LEGEND,
    MONTHLY_REPORT_OVERALL,
    MONTHS_TR,
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
    YEARLY_REPORT_BEST_MONTH,
    YEARLY_REPORT_EMPTY,
    YEARLY_REPORT_HEADER,
    YEARLY_REPORT_INVALID_ARG,
    YEARLY_REPORT_MONTH_EMPTY,
    YEARLY_REPORT_MONTH_LINE,
    YEARLY_REPORT_OVERALL,
    YEARLY_REPORT_WORST_MONTH,
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


async def cmd_monthly_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_message is not None
    user_id = await _ensure_user_id(context, update)
    args = context.args or []
    if args:
        parsed = _parse_month_arg(args)
        if parsed is None:
            await update.effective_message.reply_text(MONTHLY_REPORT_INVALID_ARG)
            return
        year, month = parsed
    else:
        year, month = await _current_year_month(user_id)
    text, keyboard = await _monthly_payload(user_id, year, month)
    await update.effective_message.reply_text(text, reply_markup=keyboard)


async def cmd_yearly_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_message is not None
    user_id = await _ensure_user_id(context, update)
    args = context.args or []
    if args:
        year = _parse_year_arg(args)
        if year is None:
            await update.effective_message.reply_text(YEARLY_REPORT_INVALID_ARG)
            return
    else:
        year, _ = await _current_year_month(user_id)
    text, keyboard = await _yearly_payload(user_id, year)
    await update.effective_message.reply_text(text, reply_markup=keyboard)


async def show_report(
    update: Update, context: ContextTypes.DEFAULT_TYPE, parsed: UICallback
) -> None:
    assert update.callback_query is not None
    user_id = await _ensure_user_id(context, update)
    if parsed.report_action is ReportAction.WEEKLY:
        text, keyboard = await _weekly_payload(user_id)
    elif parsed.report_action in (ReportAction.MONTHLY, ReportAction.MONTHLY_NAV):
        if parsed.year is None or parsed.month is None:
            year, month = await _current_year_month(user_id)
        else:
            year, month = parsed.year, parsed.month
        text, keyboard = await _monthly_payload(user_id, year, month)
    else:
        text, keyboard = await _daily_payload(user_id)
    await update.callback_query.edit_message_text(text, reply_markup=keyboard)
    await update.callback_query.answer()


async def _daily_payload(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    async with unit_of_work() as session:
        data = await report_service.generate_daily_report(session, user_id)
    return _format_daily(data), report_menu()


async def _weekly_payload(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    async with unit_of_work() as session:
        data = await report_service.generate_weekly_report(session, user_id)
    return _format_weekly(data), report_menu()


async def _current_year_month(user_id: int) -> tuple[int, int]:
    async with unit_of_work() as session:
        user = await settings_service.get_settings(session, user_id)
    now = now_in(user.timezone)
    return now.year, now.month


def _parse_month_arg(args: list[str]) -> tuple[int, int] | None:
    if len(args) != 1:
        return None
    try:
        year_str, month_str = args[0].split("-")
        year = int(year_str)
        month = int(month_str)
    except ValueError:
        return None
    if year < 1 or not 1 <= month <= 12:
        return None
    return year, month


def _parse_year_arg(args: list[str]) -> int | None:
    if len(args) != 1:
        return None
    try:
        year = int(args[0])
    except ValueError:
        return None
    if not 2000 <= year <= 2100:
        return None
    return year


async def _monthly_payload(user_id: int, year: int, month: int) -> tuple[str, InlineKeyboardMarkup]:
    async with unit_of_work() as session:
        report = await report_service.generate_monthly_report(session, user_id, year, month)
    return _format_monthly_report(report), monthly_report_nav(year, month)


async def _yearly_payload(user_id: int, year: int) -> tuple[str, InlineKeyboardMarkup]:
    async with unit_of_work() as session:
        report = await report_service.generate_yearly_report(session, user_id, year)
    return _format_yearly_report(report), report_menu()


def _format_monthly_report(report: MonthlyReport) -> str:
    month_label = f"{MONTHS_TR[report.month - 1]} {report.year}"
    if report.total == 0:
        return MONTHLY_REPORT_EMPTY.format(month_label=month_label)
    lines = [
        MONTHLY_REPORT_HEADER.format(month_label=month_label),
        "",
        MONTHLY_REPORT_OVERALL.format(
            rate=f"{report.completion_rate:.0f}",
            completed=report.total_completed,
            total=report.total,
        ),
        "",
    ]
    for stats in report.bot_stats:
        bot_key = BotKey(stats.bot_key)
        lines.append(
            MONTHLY_REPORT_BOT_LINE.format(
                icon=BOT_ICONS.get(bot_key, "📌"),
                name=BOT_KEYS_TR[bot_key],
                rate=f"{stats.completion_rate:.0f}",
                completed=stats.completed,
                total=stats.total,
            )
        )
    lines.append("")
    lines.append(
        MONTHLY_REPORT_LEGEND.format(
            completed=report.total_completed,
            missed=report.total_missed,
            pending=report.total_pending,
        )
    )
    return "\n".join(lines)


def _format_yearly_report(report: YearlyReport) -> str:
    if report.total == 0:
        return YEARLY_REPORT_EMPTY.format(year=report.year)
    lines = [
        YEARLY_REPORT_HEADER.format(year=report.year),
        "",
        YEARLY_REPORT_OVERALL.format(
            rate=f"{report.completion_rate:.0f}",
            completed=report.total_completed,
            total=report.total,
        ),
        "",
    ]
    for month in report.monthly:
        month_label = MONTHS_TR[month.month - 1]
        if month.total == 0:
            lines.append(YEARLY_REPORT_MONTH_EMPTY.format(month=month_label))
        else:
            lines.append(
                YEARLY_REPORT_MONTH_LINE.format(
                    month=month_label,
                    rate=f"{month.completion_rate:.0f}",
                    completed=month.completed,
                    total=month.total,
                )
            )
    if report.best_month is not None:
        lines.append("")
        lines.append(
            YEARLY_REPORT_BEST_MONTH.format(
                month=MONTHS_TR[report.best_month.month - 1],
                rate=f"{report.best_month.completion_rate:.0f}",
            )
        )
    if report.worst_month is not None:
        lines.append(
            YEARLY_REPORT_WORST_MONTH.format(
                month=MONTHS_TR[report.worst_month.month - 1],
                rate=f"{report.worst_month.completion_rate:.0f}",
            )
        )
    return "\n".join(lines)


def _format_daily(data: DailyReport) -> str:
    step_steps = data["step_steps"]
    step_goal = data["step_goal"]
    if data["total"] == 0 and (step_steps is None or step_goal is None):
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
    if step_steps is not None and step_goal is not None:
        pct = round(step_steps * 100 / step_goal) if step_goal > 0 else 0
        lines.append("")
        lines.append(
            DAILY_REPORT_STEP_LINE.format(
                steps=f"{step_steps:,}".replace(",", "."),
                goal=f"{step_goal:,}".replace(",", "."),
                pct=pct,
            )
        )
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
    "cmd_monthly_report",
    "cmd_rapor",
    "cmd_yearly_report",
    "show_report",
]
