from telegram import InlineKeyboardMarkup

from app.models import StepSettings
from app.tgbot.keyboards import step_menu, step_settings_detail


def _step_settings(is_active: bool = True) -> StepSettings:
    return StepSettings(
        user_id=1,
        daily_target=8000,
        reminder_hour=21,
        reminder_minute=0,
        days_of_week="1,2,3,4,5,6,7",
        is_active=is_active,
    )


def _callback_data(keyboard: InlineKeyboardMarkup) -> list[str]:
    data: list[str] = []
    for row in keyboard.inline_keyboard:
        for button in row:
            if button.callback_data is not None:
                data.append(str(button.callback_data))
    return data


def test_step_menu_rows_and_buttons() -> None:
    keyboard = step_menu()
    rows = keyboard.inline_keyboard

    assert len(rows) == 2
    assert len(rows[0]) == 2
    assert len(rows[1]) == 1


def test_step_menu_callback_data() -> None:
    data = _callback_data(step_menu())

    assert "ui:step:log" in data
    assert "ui:step:settings" in data
    assert "ui:menu" in data


def test_step_settings_detail_active() -> None:
    keyboard = step_settings_detail(_step_settings(is_active=True))
    data = _callback_data(keyboard)

    assert "ui:step:goal" in data
    assert "ui:step:time" in data
    assert "ui:step:days" in data
    assert "ui:step:toggle" in data
    assert "ui:step:menu" in data

    toggle_button = keyboard.inline_keyboard[1][1]
    assert toggle_button.text == "⏸️ Pasif Et"


def test_step_settings_detail_inactive() -> None:
    keyboard = step_settings_detail(_step_settings(is_active=False))

    toggle_button = keyboard.inline_keyboard[1][1]
    assert toggle_button.text == "▶️ Aktif Et"
