from app.services.report_service import DailyReport
from app.tgbot.messages import (
    DAILY_REPORT_STEP_LINE,
    REPORT_DAILY_TITLE,
    REPORT_EMPTY,
)
from app.tgbot.report_handlers import _format_daily


def _empty_day() -> DailyReport:
    return DailyReport(
        date="2026-08-02",
        total=0,
        completed=0,
        missed=0,
        unanswered=0,
        completed_items=[],
        missed_items=[],
        step_steps=None,
        step_goal=None,
    )


def test_format_daily_empty_without_step() -> None:
    text = _format_daily(_empty_day())
    assert text == f"{REPORT_DAILY_TITLE}\n\n{REPORT_EMPTY}"


def test_format_daily_empty_with_step() -> None:
    data = _empty_day()
    data["step_steps"] = 7500
    data["step_goal"] = 8000

    text = _format_daily(data)

    assert REPORT_DAILY_TITLE in text
    assert REPORT_EMPTY not in text
    assert DAILY_REPORT_STEP_LINE.format(steps="7.500", goal="8.000", pct=94) in text


def test_format_daily_step_goal_zero() -> None:
    data = _empty_day()
    data["step_steps"] = 500
    data["step_goal"] = 0

    text = _format_daily(data)

    assert DAILY_REPORT_STEP_LINE.format(steps="500", goal="0", pct=0) in text


def test_format_daily_with_events_and_step() -> None:
    data = _empty_day()
    data["total"] = 1
    data["completed"] = 1
    data["completed_items"] = ["Su iç"]
    data["step_steps"] = 7500
    data["step_goal"] = 8000

    text = _format_daily(data)

    assert DAILY_REPORT_STEP_LINE.format(steps="7.500", goal="8.000", pct=94) in text
    assert "✅ Su iç" in text
