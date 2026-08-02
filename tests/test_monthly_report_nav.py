from telegram import InlineKeyboardMarkup

from app.tgbot.callback_parser import ReportAction, UICallbackKind, format_report_ui, parse_ui
from app.tgbot.keyboards import monthly_report_nav, report_menu


def _flat(markup: InlineKeyboardMarkup) -> list[tuple[str, str]]:
    return [(b.text, str(b.callback_data or "")) for row in markup.inline_keyboard for b in row]


def test_nav_normal_month() -> None:
    flat = _flat(monthly_report_nav(2026, 8))

    assert flat == [
        ("◀️ Önceki Ay", "ui:reports:nav:2026-07"),
        ("Sonraki Ay ▶️", "ui:reports:nav:2026-09"),
    ]


def test_nav_january_prev_wraps_year() -> None:
    flat = _flat(monthly_report_nav(2026, 1))

    assert flat[0][1] == "ui:reports:nav:2025-12"
    assert flat[1][1] == "ui:reports:nav:2026-02"


def test_nav_december_next_wraps_year() -> None:
    flat = _flat(monthly_report_nav(2026, 12))

    assert flat[0][1] == "ui:reports:nav:2026-11"
    assert flat[1][1] == "ui:reports:nav:2027-01"


def test_format_monthly_ui_roundtrip() -> None:
    data = format_report_ui(ReportAction.MONTHLY, 2026, 8)

    parsed = parse_ui(data)

    assert parsed is not None
    assert parsed.kind is UICallbackKind.REPORTS
    assert parsed.report_action is ReportAction.MONTHLY
    assert parsed.year == 2026
    assert parsed.month == 8


def test_format_nav_ui_roundtrip() -> None:
    data = format_report_ui(ReportAction.MONTHLY_NAV, 2027, 1)

    parsed = parse_ui(data)

    assert parsed is not None
    assert parsed.report_action is ReportAction.MONTHLY_NAV
    assert parsed.year == 2027
    assert parsed.month == 1


def test_parse_monthly_without_date_ok() -> None:
    parsed = parse_ui("ui:reports:monthly")

    assert parsed is not None
    assert parsed.report_action is ReportAction.MONTHLY
    assert parsed.year is None
    assert parsed.month is None


def test_parse_monthly_invalid_month_rejected() -> None:
    assert parse_ui("ui:reports:monthly:2026-13") is None
    assert parse_ui("ui:reports:monthly:2026-00") is None


def test_parse_nav_requires_date() -> None:
    assert parse_ui("ui:reports:nav") is None
    assert parse_ui("ui:reports:nav:2026-13") is None


def test_parse_daily_unchanged() -> None:
    parsed = parse_ui("ui:reports:daily")

    assert parsed is not None
    assert parsed.report_action is ReportAction.DAILY
    assert parsed.year is None
    assert parsed.month is None


def test_report_menu_has_monthly_button() -> None:
    flat = _flat(report_menu())

    assert ("📊 Aylık", "ui:reports:monthly") in flat
    assert ("📅 Bugün", "ui:reports:daily") in flat
    assert ("📈 Haftalık", "ui:reports:weekly") in flat
