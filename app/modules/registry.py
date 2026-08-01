from __future__ import annotations

from app.models import BotKey
from app.modules.base import ReminderModule
from app.modules.habit import HabitModule

_MODULES: list[ReminderModule] = []


def register_module(module: ReminderModule) -> None:
    _MODULES.append(module)


def get_modules() -> tuple[ReminderModule, ...]:
    return tuple(_MODULES)


def get_module_by_bot_key(bot_key: BotKey) -> ReminderModule | None:
    for module in _MODULES:
        if module.bot_key == bot_key:
            return module
    return None


def get_module_by_related_type(related_type: str | None) -> ReminderModule | None:
    if related_type is None:
        return None
    for module in _MODULES:
        if module.related_type == related_type:
            return module
    return None


def setup_default_modules() -> None:
    _MODULES.clear()
    register_module(HabitModule())


__all__ = [
    "get_module_by_bot_key",
    "get_module_by_related_type",
    "get_modules",
    "register_module",
    "setup_default_modules",
]
