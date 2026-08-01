"""Weekly schedule helpers shared by reminder modules."""


def parse_days(days_of_week: str) -> set[int]:
    days: set[int] = set()
    for part in days_of_week.split(","):
        part = part.strip()
        if part.isdigit():
            days.add(int(part))
    return days


__all__ = ["parse_days"]
