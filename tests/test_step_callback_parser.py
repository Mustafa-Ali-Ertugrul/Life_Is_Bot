from app.tgbot.callback_parser import (
    StepAction,
    UICallback,
    UICallbackKind,
    format_step_ui,
    parse,
    parse_ui,
)


def test_format_step_ui_menu() -> None:
    assert format_step_ui(StepAction.MENU) == "ui:step:menu"


def test_format_step_ui_settings() -> None:
    assert format_step_ui(StepAction.SETTINGS) == "ui:step:settings"


def test_format_step_ui_log() -> None:
    assert format_step_ui(StepAction.LOG) == "ui:step:log"


def test_parse_ui_step_menu() -> None:
    parsed = parse_ui("ui:step:menu")

    assert parsed is not None
    assert parsed.kind is UICallbackKind.STEP
    assert parsed.step_action is StepAction.MENU


def test_parse_ui_step_settings() -> None:
    parsed = parse_ui("ui:step:settings")

    assert parsed is not None
    assert parsed.kind is UICallbackKind.STEP
    assert parsed.step_action is StepAction.SETTINGS


def test_parse_ui_step_toggle() -> None:
    parsed = parse_ui("ui:step:toggle")

    assert parsed is not None
    assert parsed.kind is UICallbackKind.STEP
    assert parsed.step_action is StepAction.TOGGLE


def test_parse_ui_step_log() -> None:
    parsed = parse_ui("ui:step:log")

    assert parsed is not None
    assert parsed.kind is UICallbackKind.STEP
    assert parsed.step_action is StepAction.LOG


def test_parse_ui_step_invalid_action_returns_none() -> None:
    assert parse_ui("ui:step:invalid") is None


def test_parse_ui_step_without_action_returns_none() -> None:
    assert parse_ui("ui:step") is None


def test_parse_step_ui_via_parse() -> None:
    parsed = parse("ui:step:days")

    assert isinstance(parsed, UICallback)
    assert parsed.kind is UICallbackKind.STEP
    assert parsed.step_action is StepAction.DAYS


def test_existing_parse_regression() -> None:
    parsed = parse_ui("ui:supplement:menu")

    assert parsed is not None
    assert parsed.kind is UICallbackKind.SUPPLEMENT
    assert parsed.supplement_action is not None
