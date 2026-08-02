from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.timezone import now_in, to_utc_scheduled

NY = ZoneInfo("America/New_York")
IST = ZoneInfo("Europe/Istanbul")


def test_now_in_istanbul_offset() -> None:
    assert now_in("Europe/Istanbul").utcoffset() == timedelta(hours=3)


def test_new_york_winter_offset() -> None:
    dt = datetime(2026, 1, 15, 12, tzinfo=NY)
    assert dt.utcoffset() == timedelta(hours=-5)


def test_new_york_summer_offset() -> None:
    dt = datetime(2026, 7, 15, 12, tzinfo=NY)
    assert dt.utcoffset() == timedelta(hours=-4)


def test_istanbul_no_dst() -> None:
    winter = datetime(2026, 1, 15, 12, tzinfo=IST)
    summer = datetime(2026, 7, 15, 12, tzinfo=IST)
    assert winter.utcoffset() == summer.utcoffset() == timedelta(hours=3)


def test_spring_forward_default_fold_is_est() -> None:
    dt = datetime(2026, 3, 8, 2, 30, tzinfo=NY)
    assert dt.utcoffset() == timedelta(hours=-5)


def test_fall_back_fold0_is_edt() -> None:
    dt = datetime(2026, 11, 1, 1, 30, tzinfo=NY, fold=0)
    assert dt.utcoffset() == timedelta(hours=-4)


def test_fall_back_fold1_is_est() -> None:
    dt = datetime(2026, 11, 1, 1, 30, tzinfo=NY, fold=1)
    assert dt.utcoffset() == timedelta(hours=-5)


def test_to_utc_scheduled_normal_day() -> None:
    local = datetime(2026, 6, 15, 8, 0, tzinfo=NY)
    assert to_utc_scheduled(local) == datetime(2026, 6, 15, 12, 0, tzinfo=UTC)


def test_to_utc_scheduled_spring_forward_shifts_forward() -> None:
    local = datetime(2026, 3, 8, 2, 30, tzinfo=NY)
    result = to_utc_scheduled(local)
    assert result == datetime(2026, 3, 8, 7, 30, tzinfo=UTC)
    assert result.astimezone(NY).hour == 3
    assert result.astimezone(NY).minute == 30
    assert result.astimezone(NY).utcoffset() == timedelta(hours=-4)


def test_to_utc_scheduled_fall_back_fold0_first_occurrence() -> None:
    local = datetime(2026, 11, 1, 1, 30, tzinfo=NY, fold=0)
    assert to_utc_scheduled(local) == datetime(2026, 11, 1, 5, 30, tzinfo=UTC)
