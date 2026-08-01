from datetime import date

import pytest

from app.core.supplement import (
    MAX_DURATION_DAYS,
    format_duration_range,
    format_supplement_duration,
    normalize_with_food_input,
    parse_duration_days,
    with_food_label,
)
from app.models.supplement_plan import SupplementPlan


def test_normalize_with_food_input_empty() -> None:
    assert normalize_with_food_input("aç") == "empty"
    assert normalize_with_food_input("AÇ") == "empty"
    assert normalize_with_food_input("aç karnına") == "empty"
    assert normalize_with_food_input("ac karnina") == "empty"
    assert normalize_with_food_input("empty") == "empty"


def test_normalize_with_food_input_full() -> None:
    assert normalize_with_food_input("tok") == "full"
    assert normalize_with_food_input("Tok karnına") == "full"
    assert normalize_with_food_input("tok karnina") == "full"
    assert normalize_with_food_input("full") == "full"


def test_normalize_with_food_input_any() -> None:
    assert normalize_with_food_input("farketmez") == "any"
    assert normalize_with_food_input("fark etmez") == "any"
    assert normalize_with_food_input("any") == "any"
    assert normalize_with_food_input("herhangi") == "any"


def test_normalize_with_food_input_unknown_returns_none() -> None:
    assert normalize_with_food_input("foo") is None
    assert normalize_with_food_input("") is None


def test_with_food_label() -> None:
    assert with_food_label("empty") == "Aç karnına"
    assert with_food_label("full") == "Tok karnına"
    assert with_food_label("any") == "Fark etmez"
    assert with_food_label("bilinmeyen") == "Fark etmez"


def test_parse_duration_days_valid() -> None:
    assert parse_duration_days("0") == 0
    assert parse_duration_days("14") == 14
    assert parse_duration_days("30") == 30
    assert parse_duration_days(" 7 ") == 7


def test_parse_duration_days_invalid_raises() -> None:
    for raw in ("-1", "abc", "", "1.5", "14 gün"):
        with pytest.raises(ValueError):
            parse_duration_days(raw)


def test_parse_duration_days_too_long_raises() -> None:
    with pytest.raises(ValueError):
        parse_duration_days(str(MAX_DURATION_DAYS + 1))


def test_format_duration_range_permanent() -> None:
    assert format_duration_range(0, None, None) == "Süresiz"
    assert format_duration_range(14, None, None) == "Süresiz"


def test_format_duration_range_dated() -> None:
    assert (
        format_duration_range(14, date(2026, 8, 2), date(2026, 8, 15))
        == "14 gün (02.08.2026 - 15.08.2026)"
    )


def test_format_supplement_duration_permanent() -> None:
    plan = SupplementPlan(
        user_id=1,
        name="Omega-3",
        with_food="any",
        target_hour=9,
        target_minute=0,
        days_of_week="1,2,3,4,5,6,7",
        start_date=None,
        end_date=None,
        is_active=True,
    )

    assert format_supplement_duration(plan) == "Süresiz"


def test_format_supplement_duration_dated() -> None:
    plan = SupplementPlan(
        user_id=1,
        name="Omega-3",
        with_food="any",
        target_hour=9,
        target_minute=0,
        days_of_week="1,2,3,4,5,6,7",
        start_date=date(2026, 8, 2),
        end_date=date(2026, 8, 15),
        is_active=True,
    )

    assert format_supplement_duration(plan) == "14 gün (02.08.2026 - 15.08.2026)"
