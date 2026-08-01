import pytest

from app.core.schedule import format_days, parse_days, parse_time, parse_user_days


def test_parse_days_numbers() -> None:
    assert parse_days("1,2,3,4,5") == {1, 2, 3, 4, 5}


def test_parse_days_ignores_invalid() -> None:
    assert parse_days("1,,abc,7") == {1, 7}


def test_parse_user_days_numbers() -> None:
    assert parse_user_days("1,3,5") == [1, 3, 5]


def test_parse_user_days_full_names() -> None:
    assert parse_user_days("Pazartesi, Çarşamba, Cuma") == [1, 3, 5]


def test_parse_user_days_abbreviations() -> None:
    assert parse_user_days("pzt çar cum") == [1, 3, 5]
    assert parse_user_days("paz") == [7]
    assert parse_user_days("cmt") == [6]


def test_parse_user_days_mixed() -> None:
    assert parse_user_days("pzt,3, Cuma") == [1, 3, 5]


def test_parse_user_days_sorts() -> None:
    assert parse_user_days("5,1,3") == [1, 3, 5]


def test_parse_user_days_every_day() -> None:
    assert parse_user_days("her gün") == [1, 2, 3, 4, 5, 6, 7]
    assert parse_user_days("Her gün") == [1, 2, 3, 4, 5, 6, 7]
    assert parse_user_days("hergun") == [1, 2, 3, 4, 5, 6, 7]


def test_parse_user_days_invalid_raises() -> None:
    with pytest.raises(ValueError):
        parse_user_days("bilinmeyen")
    with pytest.raises(ValueError):
        parse_user_days("8")


def test_parse_time_colon() -> None:
    assert parse_time("19:00") == (19, 0)
    assert parse_time("9:30") == (9, 30)


def test_parse_time_dot() -> None:
    assert parse_time("19.00") == (19, 0)


def test_parse_time_compact() -> None:
    assert parse_time("1900") == (19, 0)


def test_parse_time_invalid_raises() -> None:
    for raw in ("25:00", "19:60", "abc", "", "9:3"):
        with pytest.raises(ValueError):
            parse_time(raw)


def test_format_days() -> None:
    assert format_days([1, 3, 5]) == "1,3,5"
    assert format_days([5, 1, 3]) == "1,3,5"
