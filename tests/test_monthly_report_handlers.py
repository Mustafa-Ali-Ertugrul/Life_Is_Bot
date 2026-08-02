from app.services.report_service import BotMonthlyStats, MonthlyReport
from app.tgbot.report_handlers import _format_monthly_report, _parse_month_arg


def test_parse_month_arg_valid() -> None:
    assert _parse_month_arg(["2026-08"]) == (2026, 8)


def test_parse_month_arg_valid_single_digit_month() -> None:
    assert _parse_month_arg(["2026-8"]) == (2026, 8)


def test_parse_month_arg_invalid_month() -> None:
    assert _parse_month_arg(["2026-13"]) is None
    assert _parse_month_arg(["2026-00"]) is None


def test_parse_month_arg_invalid_format() -> None:
    assert _parse_month_arg(["abc"]) is None
    assert _parse_month_arg(["2026"]) is None
    assert _parse_month_arg(["2026-08", "extra"]) is None
    assert _parse_month_arg([]) is None


def test_format_monthly_report_empty() -> None:
    report = MonthlyReport(user_id=1, year=2026, month=8, bot_stats=[])

    text = _format_monthly_report(report)

    assert "Ağustos 2026" in text
    assert "Bu ay için henüz veri yok." in text


def test_format_monthly_report_full() -> None:
    report = MonthlyReport(
        user_id=1,
        year=2026,
        month=8,
        bot_stats=[
            BotMonthlyStats(
                bot_key="habit_bot",
                total=2,
                completed=2,
                missed=0,
                snoozed=0,
                pending=0,
            ),
            BotMonthlyStats(
                bot_key="sport_bot",
                total=2,
                completed=1,
                missed=1,
                snoozed=0,
                pending=0,
            ),
        ],
    )

    text = _format_monthly_report(report)

    assert "Aylık Rapor — Ağustos 2026" in text
    assert "%75 (3/4)" in text
    assert "🔁 Rutin: %100 (2/2)" in text
    assert "🏃 Spor: %50 (1/2)" in text
    assert "Tamamlanan: 3" in text
    assert "Kaçırılan: 1" in text
    assert "Bekleyen: 0" in text


def test_format_monthly_report_january_label() -> None:
    report = MonthlyReport(user_id=1, year=2026, month=1, bot_stats=[])

    text = _format_monthly_report(report)

    assert "Ocak 2026" in text


def test_format_monthly_report_december_label() -> None:
    report = MonthlyReport(user_id=1, year=2026, month=12, bot_stats=[])

    text = _format_monthly_report(report)

    assert "Aralık 2026" in text
