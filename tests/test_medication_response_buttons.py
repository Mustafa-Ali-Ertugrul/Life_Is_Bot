from datetime import datetime

from telegram import InlineKeyboardMarkup

from app.models import BotKey, ReminderEvent, ReminderStatus
from app.tgbot.keyboards import medication_response_buttons
from app.tgbot.notifier import build_reminder_message


def _event(
    bot_key: BotKey,
    event_id: int = 1,
    related_type: str | None = None,
    interpretation_json: str = "",
) -> ReminderEvent:
    return ReminderEvent(
        id=event_id,
        user_id=1,
        bot_key=bot_key.value,
        related_type=related_type or f"{bot_key.value}_plan",
        related_id=1,
        scheduled_at=datetime(2026, 8, 1, 9, 0),
        status=ReminderStatus.SCHEDULED.value,
        interpretation_json=interpretation_json,
        created_at=datetime(2026, 8, 1, 0, 0),
    )


def _flat(keyboard: InlineKeyboardMarkup) -> list[tuple[str, str]]:
    return [(b.text, str(b.callback_data or "")) for row in keyboard.inline_keyboard for b in row]


def test_medication_response_buttons_labels() -> None:
    keyboard = medication_response_buttons(42)

    flat = _flat(keyboard)
    assert len(flat) == 2
    assert flat[0][0] == "✅ Aldım"
    assert flat[1][0] == "❌ Almadım"


def test_medication_response_buttons_callback_data() -> None:
    keyboard = medication_response_buttons(42)

    flat = _flat(keyboard)
    assert flat[0][1] == "r:42:t"
    assert flat[1][1] == "r:42:f"


def test_build_reminder_message_medication_uses_taken_buttons() -> None:
    event = _event(
        BotKey.MEDICATION,
        event_id=7,
        related_type="medication_plan",
        interpretation_json='{"name": "Metformin"}',
    )

    text, keyboard = build_reminder_message(event)

    assert "İlaç" in text
    assert "Metformin" in text
    flat = _flat(keyboard)
    assert [b[1] for b in flat] == ["r:7:t", "r:7:f"]


def test_build_reminder_message_habit_keeps_existing_buttons() -> None:
    event = _event(BotKey.HABIT, event_id=3, interpretation_json='{"habit_name": "Sabah sporu"}')

    _, keyboard = build_reminder_message(event)

    flat = _flat(keyboard)
    assert [b[1] for b in flat] == ["r:3:d", "r:3:n", "r:3:s10", "r:3:x"]
    assert [b[0] for b in flat] == ["✅", "❌", "⏰ 10 dk", "⏭️"]


def test_build_reminder_message_sport_keeps_existing_buttons() -> None:
    event = _event(BotKey.SPORT, event_id=4)

    _, keyboard = build_reminder_message(event)

    flat = _flat(keyboard)
    assert [b[1] for b in flat] == ["r:4:d", "r:4:n", "r:4:s10", "r:4:x"]


def test_build_reminder_message_supplement_keeps_existing_buttons() -> None:
    event = _event(BotKey.SUPPLEMENT, event_id=5)

    _, keyboard = build_reminder_message(event)

    flat = _flat(keyboard)
    assert [b[1] for b in flat] == ["r:5:d", "r:5:n", "r:5:s10", "r:5:x"]


def test_build_reminder_message_step_keeps_existing_buttons() -> None:
    event = _event(BotKey.STEP, event_id=6)

    _, keyboard = build_reminder_message(event)

    flat = _flat(keyboard)
    assert [b[1] for b in flat] == ["r:6:d", "r:6:n", "r:6:s10", "r:6:x"]
