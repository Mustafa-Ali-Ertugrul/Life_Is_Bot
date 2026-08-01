"""Supplement plan UI helpers shared by handlers and tests."""

from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.supplement_plan import SupplementPlan

MAX_DURATION_DAYS = 365

_WITH_FOOD_EMPTY = {"aç", "ac", "aç karnına", "ac karnina", "empty"}
_WITH_FOOD_FULL = {"tok", "tok karnına", "tok karnina", "full"}
_WITH_FOOD_ANY = {"farketmez", "fark etmez", "any", "herhangi"}


def normalize_with_food_input(value: str) -> str | None:
    text = value.strip().lower()
    if text in _WITH_FOOD_EMPTY:
        return "empty"
    if text in _WITH_FOOD_FULL:
        return "full"
    if text in _WITH_FOOD_ANY:
        return "any"
    return None


def with_food_label(value: str) -> str:
    if value == "empty":
        return "Aç karnına"
    if value == "full":
        return "Tok karnına"
    return "Fark etmez"


def parse_duration_days(value: str) -> int:
    text = value.strip()
    if not text.isdigit():
        raise ValueError("invalid duration")
    days = int(text)
    if days > MAX_DURATION_DAYS:
        raise ValueError("duration too long")
    return days


def format_duration_range(days: int, start_date: date | None, end_date: date | None) -> str:
    if days == 0 or start_date is None or end_date is None:
        return "Süresiz"
    return f"{days} gün ({start_date:%d.%m.%Y} - {end_date:%d.%m.%Y})"


def format_supplement_duration(plan: "SupplementPlan") -> str:
    if plan.start_date is None or plan.end_date is None:
        return "Süresiz"
    days = (plan.end_date - plan.start_date).days + 1
    return format_duration_range(days, plan.start_date, plan.end_date)


__all__ = [
    "MAX_DURATION_DAYS",
    "format_duration_range",
    "format_supplement_duration",
    "normalize_with_food_input",
    "parse_duration_days",
    "with_food_label",
]
