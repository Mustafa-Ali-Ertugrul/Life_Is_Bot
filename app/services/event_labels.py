import json

from app.models import ReminderEvent


def event_label(event: ReminderEvent) -> str:
    if event.related_type == "habit":
        try:
            data = json.loads(event.interpretation_json or "{}")
        except ValueError:
            data = {}
        name = data.get("habit_name")
        if name:
            return str(name)
    return event.related_type or "hatırlatma"


__all__ = ["event_label"]
