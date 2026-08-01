"""Weekly schedule helpers shared by reminder modules."""

import re

DAY_NAMES: dict[str, int] = {
    "pazartesi": 1,
    "pzt": 1,
    "sali": 2,
    "sal": 2,
    "carsamba": 3,
    "car": 3,
    "persembe": 4,
    "per": 4,
    "cuma": 5,
    "cum": 5,
    "cumartesi": 6,
    "cmt": 6,
    "pazar": 7,
    "paz": 7,
}

_TRANSLIT = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")

_TIME_RE = re.compile(r"^([01]?\d|2[0-3])[:.]([0-5]\d)$")
_TIME_COMPACT_RE = re.compile(r"^([01]\d|2[0-3])([0-5]\d)$")


def parse_days(days_of_week: str) -> set[int]:
    days: set[int] = set()
    for part in days_of_week.split(","):
        part = part.strip()
        if part.isdigit():
            days.add(int(part))
    return days


def parse_user_days(value: str) -> list[int]:
    days: set[int] = set()
    for part in re.split(r"[,/\s]+", value.strip()):
        if not part:
            continue
        normalized = part.lower().translate(_TRANSLIT)
        day = DAY_NAMES.get(normalized)
        if day is None and normalized.isdigit():
            parsed = int(normalized)
            if 1 <= parsed <= 7:
                day = parsed
        if day is None:
            raise ValueError(f"Bilinmeyen gün: {part}")
        days.add(day)
    if not days:
        raise ValueError("Gün listesi boş")
    return sorted(days)


def parse_time(value: str) -> tuple[int, int]:
    raw = value.strip()
    match = _TIME_RE.match(raw)
    if match is not None:
        return int(match.group(1)), int(match.group(2))
    match = _TIME_COMPACT_RE.match(raw)
    if match is not None:
        return int(match.group(1)), int(match.group(2))
    raise ValueError(f"Geçersiz saat: {value}")


def format_days(days: list[int]) -> str:
    return ",".join(str(day) for day in sorted(days))


__all__ = ["DAY_NAMES", "format_days", "parse_days", "parse_time", "parse_user_days"]
