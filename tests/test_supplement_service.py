from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone import get_user_timezone, now_in
from app.models import BotKey, ReminderEvent, ReminderStatus
from app.services import preference_service, supplement_service, user_service
from tests.conftest import TELEGRAM_USER_ID


async def _user(db_session: AsyncSession) -> int:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    return user.id


async def test_create_and_list_supplement_plans(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await supplement_service.create_supplement_plan(
        db_session, user_id, "D Vitamini", "1,3,5", 9, 0, dose="1 damla"
    )

    plans = await supplement_service.list_supplement_plans(db_session, user_id)

    assert len(plans) == 1
    assert plans[0].name == "D Vitamini"
    assert plans[0].dose == "1 damla"
    assert plans[0].with_food == "any"
    assert plans[0].target_hour == 9
    assert plans[0].target_minute == 0
    assert plans[0].days_of_week == "1,3,5"
    assert plans[0].is_active is True


async def test_create_supplement_plan_enables_supplement_preference(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session)
    plan = await supplement_service.create_supplement_plan(
        db_session, user_id, "Magnezyum", "1,2,3,4,5", 21, 0
    )

    pref = await preference_service.get_preference(db_session, plan.user_id, BotKey.SUPPLEMENT)
    assert pref is not None
    assert pref.enabled is True


async def test_create_supplement_plan_normalizes_with_food(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    plan = await supplement_service.create_supplement_plan(
        db_session, user_id, "Demir", "1,2,3,4,5", 12, 0, with_food=" Full "
    )

    assert plan.with_food == "full"


async def test_create_supplement_plan_rejects_invalid_with_food(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)

    with pytest.raises(ValueError):
        await supplement_service.create_supplement_plan(
            db_session, user_id, "Demir", "1,2,3,4,5", 12, 0, with_food="breakfast"
        )


async def test_create_supplement_plan_rejects_inverted_date_range(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session)

    with pytest.raises(ValueError):
        await supplement_service.create_supplement_plan(
            db_session,
            user_id,
            "Demir",
            "1,2,3,4,5",
            12,
            0,
            start_date=date(2026, 8, 10),
            end_date=date(2026, 8, 1),
        )


async def test_get_supplement_plan(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    plan = await supplement_service.create_supplement_plan(
        db_session, user_id, "Omega-3", "1,2,3,4,5", 9, 0
    )

    found = await supplement_service.get_supplement_plan(db_session, plan.id)

    assert found is not None
    assert found.id == plan.id


async def test_toggle_supplement_plan(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    plan = await supplement_service.create_supplement_plan(
        db_session, user_id, "Omega-3", "1,2,3,4,5", 9, 0
    )

    updated = await supplement_service.toggle_supplement_plan(db_session, plan.id, False)

    assert updated is not None
    assert updated.is_active is False


async def test_toggle_supplement_plan_missing_returns_none(db_session: AsyncSession) -> None:
    updated = await supplement_service.toggle_supplement_plan(db_session, 99999, False)
    assert updated is None


async def test_generate_today_events_creates_for_matching_day(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    today = now_in()
    weekday = today.isoweekday()
    plan = await supplement_service.create_supplement_plan(
        db_session, user_id, "D Vitamini", str(weekday), 9, 0, dose="1 damla"
    )

    events = await supplement_service.generate_today_events(db_session, user_id, now=today)

    assert len(events) == 1
    event = events[0]
    assert event.bot_key == BotKey.SUPPLEMENT.value
    assert event.related_type == "supplement_plan"
    assert event.related_id == plan.id
    assert (
        event.scheduled_at.replace(tzinfo=UTC).astimezone(get_user_timezone("Europe/Istanbul")).hour
        == 9
    )
    assert '"name": "D Vitamini"' in event.interpretation_json
    assert '"with_food": "any"' in event.interpretation_json


async def test_generate_today_events_skips_outside_date_range(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    today = now_in().date()
    await supplement_service.create_supplement_plan(
        db_session,
        user_id,
        "D Vitamini",
        "1,2,3,4,5,6,7",
        9,
        0,
        start_date=today - timedelta(days=10),
        end_date=today - timedelta(days=5),
    )

    events = await supplement_service.generate_today_events(db_session, user_id)

    assert events == []


async def test_generate_today_events_skips_non_matching_day(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    today = now_in()
    other_weekday = (today.isoweekday() % 7) + 1
    await supplement_service.create_supplement_plan(
        db_session, user_id, "D Vitamini", str(other_weekday), 9, 0
    )

    events = await supplement_service.generate_today_events(db_session, user_id, now=today)

    assert events == []


async def test_generate_today_events_skips_inactive(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    today = now_in()
    weekday = today.isoweekday()
    plan = await supplement_service.create_supplement_plan(
        db_session, user_id, "D Vitamini", str(weekday), 9, 0
    )
    await supplement_service.toggle_supplement_plan(db_session, plan.id, False)

    events = await supplement_service.generate_today_events(db_session, user_id, now=today)

    assert events == []


async def test_generate_today_events_is_idempotent(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    today = now_in()
    weekday = today.isoweekday()
    await supplement_service.create_supplement_plan(
        db_session, user_id, "D Vitamini", str(weekday), 9, 0
    )

    first = await supplement_service.generate_today_events(db_session, user_id, now=today)
    second = await supplement_service.generate_today_events(db_session, user_id, now=today)

    assert len(first) == 1
    assert len(second) == 1
    assert second[0].id == first[0].id


def test_supplement_reminder_uses_supplement_label() -> None:
    from app.modules.supplement import SupplementModule

    event = ReminderEvent(
        user_id=1,
        bot_key=BotKey.SUPPLEMENT.value,
        related_type="supplement_plan",
        related_id=1,
        scheduled_at=datetime(2026, 8, 1, 9, 0),
        status=ReminderStatus.SCHEDULED.value,
        interpretation_json='{"name": "D Vitamini", "dose": "1 damla"}',
        created_at=datetime(2026, 8, 1, 0, 0),
    )

    assert SupplementModule().event_label(event) == "D Vitamini"


def test_supplement_reminder_label_falls_back_to_supplement() -> None:
    from app.modules.supplement import SupplementModule

    event = ReminderEvent(
        user_id=1,
        bot_key=BotKey.SUPPLEMENT.value,
        related_type="supplement_plan",
        related_id=1,
        scheduled_at=datetime(2026, 8, 1, 9, 0),
        status=ReminderStatus.SCHEDULED.value,
        interpretation_json="",
        created_at=datetime(2026, 8, 1, 0, 0),
    )

    assert SupplementModule().event_label(event) == "Supplement"
