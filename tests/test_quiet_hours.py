from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.quiet_hours import (
    is_valid_hhmm,
    is_within_quiet_hours,
    next_quiet_end,
    parse_hhmm,
)

IST = ZoneInfo("Europe/Istanbul")


def _dt(hour: int, minute: int) -> datetime:
    return datetime(2026, 8, 1, hour, minute, tzinfo=IST)


def test_parse_hhmm_valid() -> None:
    assert parse_hhmm("23:00") == (23, 0)
    assert parse_hhmm("07:05") == (7, 5)


def test_parse_hhmm_invalid() -> None:
    assert parse_hhmm("24:00") is None
    assert parse_hhmm("7:00") is None
    assert parse_hhmm("23:60") is None
    assert parse_hhmm("abc") is None


def test_is_valid_hhmm() -> None:
    assert is_valid_hhmm("08:00") is True
    assert is_valid_hhmm("8:00") is False
    assert is_valid_hhmm("24:00") is False


def test_quiet_hours_night_window_late_night() -> None:
    assert is_within_quiet_hours(_dt(23, 30), "23:00", "07:00") is True


def test_quiet_hours_night_window_early_morning() -> None:
    assert is_within_quiet_hours(_dt(6, 59), "23:00", "07:00") is True


def test_quiet_hours_night_window_boundary_end_excluded() -> None:
    assert is_within_quiet_hours(_dt(7, 0), "23:00", "07:00") is False
    assert is_within_quiet_hours(_dt(7, 1), "23:00", "07:00") is False


def test_quiet_hours_night_window_before_start() -> None:
    assert is_within_quiet_hours(_dt(22, 59), "23:00", "07:00") is False


def test_quiet_hours_same_day_window() -> None:
    assert is_within_quiet_hours(_dt(2, 0), "01:00", "05:00") is True
    assert is_within_quiet_hours(_dt(5, 0), "01:00", "05:00") is False


def test_quiet_hours_after_midnight() -> None:
    assert is_within_quiet_hours(_dt(0, 30), "23:00", "07:00") is True


def test_quiet_hours_same_start_end_disabled() -> None:
    assert is_within_quiet_hours(_dt(12, 0), "00:00", "00:00") is False
    assert is_within_quiet_hours(_dt(3, 0), "00:00", "00:00") is False


def test_next_quiet_end_night_window_after_midnight() -> None:
    end = next_quiet_end(_dt(23, 30), "23:00", "07:00")
    assert end == _dt(7, 0) + timedelta(days=1)


def test_next_quiet_end_night_window_same_day() -> None:
    end = next_quiet_end(_dt(6, 59), "23:00", "07:00")
    assert end == _dt(7, 0)


def test_next_quiet_end_same_day_window() -> None:
    end = next_quiet_end(_dt(2, 0), "01:00", "05:00")
    assert end == _dt(5, 0)
