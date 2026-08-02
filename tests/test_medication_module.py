from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.notification_policy import evaluate_notification
from app.models import BotKey, ReminderEvent, ReminderStatus
from app.modules.base import EventGenerationContext
from app.modules.medication import MedicationModule
from app.modules.registry import get_modules, setup_default_modules
from app.services import medication_service, user_service
from tests.conftest import TELEGRAM_USER_ID

MONDAY_UTC = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)


def test_medication_module_metadata() -> None:
    module = MedicationModule()

    assert module.bot_key == BotKey.MEDICATION
    assert module.related_type == "medication_plan"
    assert module.display_name == "İlaç"


def test_event_label_with_name_and_dose() -> None:
    event = ReminderEvent(
        user_id=1,
        bot_key=BotKey.MEDICATION.value,
        related_type="medication_plan",
        related_id=1,
        scheduled_at=datetime(2026, 8, 1, 9, 0),
        status=ReminderStatus.SCHEDULED.value,
        interpretation_json='{"name": "Metformin", "dose": "500mg"}',
        created_at=datetime(2026, 8, 1, 0, 0),
    )

    assert MedicationModule().event_label(event) == "Metformin (500mg)"


def test_event_label_with_name_only() -> None:
    event = ReminderEvent(
        user_id=1,
        bot_key=BotKey.MEDICATION.value,
        related_type="medication_plan",
        related_id=1,
        scheduled_at=datetime(2026, 8, 1, 9, 0),
        status=ReminderStatus.SCHEDULED.value,
        interpretation_json='{"name": "Metformin"}',
        created_at=datetime(2026, 8, 1, 0, 0),
    )

    assert MedicationModule().event_label(event) == "Metformin"


def test_event_label_falls_back_to_medication() -> None:
    event = ReminderEvent(
        user_id=1,
        bot_key=BotKey.MEDICATION.value,
        related_type="medication_plan",
        related_id=1,
        scheduled_at=datetime(2026, 8, 1, 9, 0),
        status=ReminderStatus.SCHEDULED.value,
        interpretation_json="",
        created_at=datetime(2026, 8, 1, 0, 0),
    )

    assert MedicationModule().event_label(event) == "İlaç"


async def test_generate_daily_events_delegates_to_service(
    db_session: AsyncSession,
) -> None:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    await medication_service.create_medication_plan(db_session, user.id, "Metformin", 9, 0, "1")

    module = MedicationModule()
    events = await module.generate_daily_events(
        db_session, EventGenerationContext(user=user, now_utc=MONDAY_UTC)
    )

    assert len(events) == 1
    assert events[0].bot_key == BotKey.MEDICATION.value


def test_setup_default_modules_includes_medication() -> None:
    setup_default_modules()

    modules = get_modules()
    assert len(modules) == 5
    assert isinstance(modules[4], MedicationModule)


async def test_medication_event_suppressed_without_global_consent(
    db_session: AsyncSession,
) -> None:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    await medication_service.create_medication_plan(db_session, user.id, "Metformin", 9, 0, "1")
    events = await medication_service.generate_today_events(db_session, user.id, now=MONDAY_UTC)

    decision = await evaluate_notification(db_session, user, events[0], MONDAY_UTC)

    assert decision["action"] == "suppress"
    assert decision["reason"] == "consent_missing"


async def test_medication_event_sends_with_global_consent(db_session: AsyncSession) -> None:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    await medication_service.create_medication_plan(db_session, user.id, "Metformin", 9, 0, "1")
    events = await medication_service.generate_today_events(db_session, user.id, now=MONDAY_UTC)
    user.consent_given = True
    await db_session.commit()

    decision = await evaluate_notification(db_session, user, events[0], MONDAY_UTC)

    assert decision["action"] == "send_now"
    assert decision["reason"] == "ok"
