from app.services.report_service import MonthlyBreakdown, YearlyReport
from app.tgbot.report_handlers import _format_yearly_report, _parse_year_arg


def test_parse_year_arg_valid() -> None:
    assert _parse_year_arg(["2026"]) == 2026


def test_parse_year_arg_out_of_range() -> None:
    assert _parse_year_arg(["1999"]) is None
    assert _parse_year_arg(["2101"]) is None


def test_parse_year_arg_invalid_format() -> None:
    assert _parse_year_arg(["abc"]) is None
    assert _parse_year_arg(["2026-08"]) is None
    assert _parse_year_arg(["2026", "extra"]) is None
    assert _parse_year_arg([]) is None


def test_format_yearly_report_empty() -> None:
    report = YearlyReport(user_id=1, year=2026)

    text = _format_yearly_report(report)

    assert "2026" in text
    assert "Bu yıl için henüz veri yok." in text


def test_format_yearly_report_full() -> None:
    report = YearlyReport(
        user_id=1,
        year=2026,
        monthly=[
            MonthlyBreakdown(
                month=3,
                total=4,
                completed=3,
                missed=1,
                snoozed=0,
                pending=0,
                completion_rate=75.0,
            ),
            MonthlyBreakdown(
                month=8,
                total=2,
                completed=0,
                missed=2,
                snoozed=0,
                pending=0,
                completion_rate=0.0,
            ),
        ],
    )

    text = _format_yearly_report(report)

    assert "Yıllık Rapor — 2026" in text
    assert "%50 (3/6)" in text
    assert "Mart: %75 (3/4)" in text
    assert "Ağustos: %0 (0/2)" in text
    assert "En iyi ay: Mart (%75)" in text
    assert "En zayıf ay: Ağustos (%0)" in text


def test_format_yearly_report_empty_months_listed() -> None:
    report = YearlyReport(
        user_id=1,
        year=2026,
        monthly=[
            MonthlyBreakdown(
                month=1,
                total=2,
                completed=2,
                missed=0,
                snoozed=0,
                pending=0,
                completion_rate=100.0,
            ),
            MonthlyBreakdown(
                month=2,
                total=0,
                completed=0,
                missed=0,
                snoozed=0,
                pending=0,
                completion_rate=0.0,
            ),
        ],
    )

    text = _format_yearly_report(report)

    assert "Ocak: %100 (2/2)" in text
    assert "Şubat: Veri yok" in text


def test_format_yearly_report_january_december_labels() -> None:
    report = YearlyReport(
        user_id=1,
        year=2026,
        monthly=[
            MonthlyBreakdown(
                month=1,
                total=1,
                completed=1,
                missed=0,
                snoozed=0,
                pending=0,
                completion_rate=100.0,
            ),
            MonthlyBreakdown(
                month=12,
                total=1,
                completed=0,
                missed=1,
                snoozed=0,
                pending=0,
                completion_rate=0.0,
            ),
        ],
    )

    text = _format_yearly_report(report)

    assert "Ocak: %100 (1/1)" in text
    assert "Aralık: %0 (0/1)" in text
