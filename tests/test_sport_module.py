from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BotKey, ReminderEvent
from app.modules.base import EventGenerationContext
from app.modules.sport import SportModule
from app.services import sport_service, user_service
from tests.conftest import TELEGRAM_USER_ID

MONDAY_UTC = datetime(2026, 8, 3, 9, 0, tzinfo=UTC)  # 2026-08-03 12:00 Europe/Istanbul


def _event(*, interpretation_json: str) -> ReminderEvent:
    return ReminderEvent(
        user_id=1,
        bot_key=BotKey.SPORT.value,
        related_type="sport_plan",
        related_id=1,
        scheduled_at=datetime(2026, 8, 3, 18, 0, tzinfo=UTC),
        scheduled_local_date=datetime(2026, 8, 3).date(),
        status="scheduled",
        interpretation_json=interpretation_json,
        created_at=datetime(2026, 8, 3, 0, 0, tzinfo=UTC),
    )


async def test_generate_daily_events_creates_event(db_session: AsyncSession) -> None:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    await sport_service.create_sport_plan(db_session, user.id, "Koşu", "1", 18, 0)

    module = SportModule()
    events = await module.generate_daily_events(
        db_session,
        EventGenerationContext(user=user, now_utc=MONDAY_UTC),
    )

    assert len(events) == 1
    assert events[0].related_type == "sport_plan"
    assert events[0].related_id is not None


async def test_generate_daily_events_skips_other_weekdays(db_session: AsyncSession) -> None:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    await sport_service.create_sport_plan(db_session, user.id, "Koşu", "2", 18, 0)

    module = SportModule()
    events = await module.generate_daily_events(
        db_session,
        EventGenerationContext(user=user, now_utc=MONDAY_UTC),
    )

    assert events == []


def test_event_label_sport_type() -> None:
    event = _event(interpretation_json='{"sport_type": "koşu"}')

    assert SportModule().event_label(event) == "Koşu antrenmanı"


def test_event_label_empty_interpretation_returns_none() -> None:
    event = _event(interpretation_json="{}")

    assert SportModule().event_label(event) is None


def test_event_label_invalid_json_returns_none() -> None:
    event = _event(interpretation_json="not-json")

    assert SportModule().event_label(event) is None
