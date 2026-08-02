from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.quiet_hours import is_within_quiet_hours, next_quiet_end

NY = ZoneInfo("America/New_York")
IST = ZoneInfo("Europe/Istanbul")


def _dt(hour: int, minute: int) -> datetime:
    return datetime(2026, 8, 1, hour, minute, tzinfo=IST)


def test_quiet_normal_window_in() -> None:
    assert is_within_quiet_hours(_dt(23, 0), "22:00", "07:00") is True


def test_quiet_normal_window_out() -> None:
    assert is_within_quiet_hours(_dt(12, 0), "22:00", "07:00") is False


def test_quiet_start_equals_end_returns_false() -> None:
    assert is_within_quiet_hours(_dt(3, 0), "03:00", "03:00") is False


def test_quiet_midnight_cross() -> None:
    assert is_within_quiet_hours(_dt(0, 30), "23:00", "06:00") is True


def test_quiet_fall_back_both_folds_in_window() -> None:
    # quiet_hours only reads hour/minute of the local wall clock, so DST
    # transitions do not change the result for either fold.
    fold0 = datetime(2026, 11, 1, 1, 30, tzinfo=NY, fold=0)
    fold1 = datetime(2026, 11, 1, 1, 30, tzinfo=NY, fold=1)
    assert is_within_quiet_hours(fold0, "00:00", "03:00") is True
    assert is_within_quiet_hours(fold1, "00:00", "03:00") is True


def test_quiet_next_quiet_end_basic() -> None:
    now = datetime(2026, 11, 1, 1, 30, tzinfo=NY, fold=0)
    end = next_quiet_end(now, "00:00", "03:00")
    assert end.hour == 3
    assert end.minute == 0
    assert end.date() == now.date()


def test_quiet_next_quiet_end_rolls_to_next_day() -> None:
    now = datetime(2026, 11, 1, 4, 30, tzinfo=NY, fold=0)
    end = next_quiet_end(now, "00:00", "03:00")
    assert end.date() == datetime(2026, 11, 2).date()
