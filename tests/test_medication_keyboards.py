from types import SimpleNamespace
from typing import cast

from app.models import MedicationPlan
from app.tgbot.keyboards import (
    medication_confirm,
    medication_menu,
    medication_plan_detail,
    medication_plan_list,
)


def _plan(plan_id: int, name: str = "Metformin", is_active: bool = True) -> MedicationPlan:
    return cast(
        MedicationPlan,
        SimpleNamespace(id=plan_id, name=name, is_active=is_active),
    )


def test_medication_menu_buttons() -> None:
    keyboard = medication_menu()
    flat = [b.callback_data for row in keyboard.inline_keyboard for b in row]
    assert flat == ["ui:med:list", "ui:med:new", "ui:menu"]


def test_medication_plan_list_buttons() -> None:
    keyboard = medication_plan_list([_plan(1, "Metformin", True), _plan(2, "Vit D", False)])
    flat = [(b.text, b.callback_data) for row in keyboard.inline_keyboard for b in row]
    assert flat[0] == ("Metformin", "ui:med:detail:1")
    assert flat[1] == ("Vit D", "ui:med:detail:2")
    assert flat[2][1] == "ui:med:new"
    assert flat[3][1] == "ui:menu"


def test_medication_plan_detail_active() -> None:
    keyboard = medication_plan_detail(_plan(1, is_active=True))
    flat = [(b.text, b.callback_data) for row in keyboard.inline_keyboard for b in row]
    assert flat[0] == ("Pasif Et", "ui:med:toggle:1")
    assert flat[1][1] == "ui:med:list"


def test_medication_plan_detail_inactive() -> None:
    keyboard = medication_plan_detail(_plan(2, is_active=False))
    flat = [(b.text, b.callback_data) for row in keyboard.inline_keyboard for b in row]
    assert flat[0] == ("Aktif Et", "ui:med:toggle:2")


def test_medication_confirm_buttons() -> None:
    keyboard = medication_confirm()
    flat = [b.callback_data for row in keyboard.inline_keyboard for b in row]
    assert flat == ["ui:med:confirm", "ui:med:cancel"]
