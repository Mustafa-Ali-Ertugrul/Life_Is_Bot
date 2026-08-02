from app.tgbot.callback_parser import (
    MedicationAction,
    UICallbackKind,
    format_medication_ui,
    parse_ui,
)


def test_format_medication_ui_menu() -> None:
    assert format_medication_ui(MedicationAction.MENU) == "ui:med:menu"


def test_format_medication_ui_detail_with_id() -> None:
    assert format_medication_ui(MedicationAction.DETAIL, 42) == "ui:med:detail:42"


def test_parse_medication_menu() -> None:
    parsed = parse_ui("ui:med:menu")
    assert parsed is not None
    assert parsed.kind is UICallbackKind.MEDICATION
    assert parsed.medication_action is MedicationAction.MENU
    assert parsed.medication_plan_id is None


def test_parse_medication_detail() -> None:
    parsed = parse_ui("ui:med:detail:42")
    assert parsed is not None
    assert parsed.kind is UICallbackKind.MEDICATION
    assert parsed.medication_action is MedicationAction.DETAIL
    assert parsed.medication_plan_id == 42


def test_parse_medication_toggle() -> None:
    parsed = parse_ui("ui:med:toggle:123")
    assert parsed is not None
    assert parsed.medication_action is MedicationAction.TOGGLE
    assert parsed.medication_plan_id == 123


def test_parse_medication_confirm() -> None:
    parsed = parse_ui("ui:med:confirm")
    assert parsed is not None
    assert parsed.medication_action is MedicationAction.CONFIRM
    assert parsed.medication_plan_id is None


def test_parse_medication_invalid_action() -> None:
    assert parse_ui("ui:med:invalid") is None


def test_parse_medication_detail_bad_id() -> None:
    assert parse_ui("ui:med:detail:abc") is None


def test_parse_medication_without_action() -> None:
    assert parse_ui("ui:med") is None


def test_parse_medication_roundtrip() -> None:
    for action in MedicationAction:
        if action in (MedicationAction.DETAIL, MedicationAction.TOGGLE):
            parsed = parse_ui(format_medication_ui(action, 7))
            assert parsed is not None
            assert parsed.medication_plan_id == 7
        else:
            assert parse_ui(format_medication_ui(action)) is not None


def test_parse_supplement_regression() -> None:
    parsed = parse_ui("ui:supplement:detail:7")
    assert parsed is not None
    assert parsed.kind is UICallbackKind.SUPPLEMENT
    assert parsed.supplement_plan_id == 7


def test_parse_step_regression() -> None:
    parsed = parse_ui("ui:step:menu")
    assert parsed is not None
    assert parsed.kind is UICallbackKind.STEP
