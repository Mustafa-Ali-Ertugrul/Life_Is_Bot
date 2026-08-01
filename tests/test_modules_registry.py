from app.models import BotKey
from app.modules.habit import HabitModule
from app.modules.registry import (
    get_module_by_bot_key,
    get_module_by_related_type,
    get_modules,
    register_module,
    setup_default_modules,
)


def test_setup_default_modules_registers_habit() -> None:
    setup_default_modules()

    modules = get_modules()
    assert len(modules) == 1
    assert isinstance(modules[0], HabitModule)


def test_get_module_by_bot_key_habit() -> None:
    setup_default_modules()

    assert isinstance(get_module_by_bot_key(BotKey.HABIT), HabitModule)


def test_get_module_by_related_type_habit() -> None:
    setup_default_modules()

    assert isinstance(get_module_by_related_type("habit"), HabitModule)


def test_get_module_by_related_type_none() -> None:
    setup_default_modules()

    assert get_module_by_related_type(None) is None


def test_get_module_by_related_type_unknown() -> None:
    setup_default_modules()

    assert get_module_by_related_type("unknown") is None


def test_get_module_by_bot_key_unregistered() -> None:
    setup_default_modules()

    assert get_module_by_bot_key(BotKey.SPORT) is None


def test_register_module_manual_registration() -> None:
    setup_default_modules()
    register_module(HabitModule())

    assert len(get_modules()) == 2
