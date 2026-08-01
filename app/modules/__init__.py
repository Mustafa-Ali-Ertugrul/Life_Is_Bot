"""Bot modules: reminder generation and labeling per bot."""

from app.modules.base import EventGenerationContext, ReminderModule
from app.modules.habit import HabitModule
from app.modules.registry import (
    get_module_by_bot_key,
    get_module_by_related_type,
    get_modules,
    register_module,
    setup_default_modules,
)

__all__ = [
    "EventGenerationContext",
    "HabitModule",
    "ReminderModule",
    "get_module_by_bot_key",
    "get_module_by_related_type",
    "get_modules",
    "register_module",
    "setup_default_modules",
]
