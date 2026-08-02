from app.models import BotKey
from app.modules.habit import HabitModule
from app.modules.medication import MedicationModule
from app.modules.registry import (
    get_module_by_bot_key,
    get_module_by_related_type,
    get_modules,
    register_module,
    setup_default_modules,
)
from app.modules.sport import SportModule
from app.modules.step import StepModule
from app.modules.supplement import SupplementModule


def test_setup_default_modules_registers_habit_sport_supplement_step_and_medication() -> None:
    setup_default_modules()

    modules = get_modules()
    assert len(modules) == 5
    assert isinstance(modules[0], HabitModule)
    assert isinstance(modules[1], SportModule)
    assert isinstance(modules[2], SupplementModule)
    assert isinstance(modules[3], StepModule)
    assert isinstance(modules[4], MedicationModule)


def test_get_module_by_bot_key_habit() -> None:
    setup_default_modules()

    assert isinstance(get_module_by_bot_key(BotKey.HABIT), HabitModule)


def test_get_module_by_bot_key_sport() -> None:
    setup_default_modules()

    assert isinstance(get_module_by_bot_key(BotKey.SPORT), SportModule)


def test_get_module_by_bot_key_supplement() -> None:
    setup_default_modules()

    assert isinstance(get_module_by_bot_key(BotKey.SUPPLEMENT), SupplementModule)


def test_get_module_by_bot_key_step() -> None:
    setup_default_modules()

    assert isinstance(get_module_by_bot_key(BotKey.STEP), StepModule)


def test_get_module_by_bot_key_medication() -> None:
    setup_default_modules()

    assert isinstance(get_module_by_bot_key(BotKey.MEDICATION), MedicationModule)


def test_get_module_by_related_type_habit() -> None:
    setup_default_modules()

    assert isinstance(get_module_by_related_type("habit"), HabitModule)


def test_get_module_by_related_type_sport() -> None:
    setup_default_modules()

    assert isinstance(get_module_by_related_type("sport_plan"), SportModule)


def test_get_module_by_related_type_supplement() -> None:
    setup_default_modules()

    assert isinstance(get_module_by_related_type("supplement_plan"), SupplementModule)


def test_get_module_by_related_type_step_goal() -> None:
    setup_default_modules()

    assert isinstance(get_module_by_related_type("step_goal"), StepModule)


def test_get_module_by_related_type_medication() -> None:
    setup_default_modules()

    assert isinstance(get_module_by_related_type("medication_plan"), MedicationModule)


def test_get_module_by_related_type_none() -> None:
    setup_default_modules()

    assert get_module_by_related_type(None) is None


def test_get_module_by_related_type_unknown() -> None:
    setup_default_modules()

    assert get_module_by_related_type("unknown") is None


def test_get_module_by_bot_key_unregistered() -> None:
    setup_default_modules()

    assert get_module_by_bot_key(BotKey.ASSESSMENT) is None


def test_register_module_manual_registration() -> None:
    setup_default_modules()
    register_module(HabitModule())

    assert len(get_modules()) == 6
