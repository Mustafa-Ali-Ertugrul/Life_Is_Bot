from app.models import ReminderEvent
from app.modules.registry import get_module_by_related_type


def event_label(event: ReminderEvent) -> str:
    module = get_module_by_related_type(event.related_type)
    if module is not None:
        label = module.event_label(event)
        if label is not None:
            return label
    return event.related_type or "hatırlatma"


__all__ = ["event_label"]
