from datetime import UTC, date, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone import get_user_timezone
from app.models import BotKey
from app.services import medication_service, preference_service, user_service
from tests.conftest import TELEGRAM_USER_ID

MONDAY_UTC = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)


async def _user(db_session: AsyncSession) -> int:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    return user.id


async def test_create_medication_plan_basic(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    plan = await medication_service.create_medication_plan(
        db_session,
        user_id,
        "Metformin",
        8,
        0,
        "1,3,5",
        dose="500mg",
        with_food="full",
        notes="aç karnına",
    )

    assert plan.name == "Metformin"
    assert plan.dose == "500mg"
    assert plan.with_food == "full"
    assert plan.target_hour == 8
    assert plan.target_minute == 0
    assert plan.days_of_week == "1,3,5"
    assert plan.is_active is True
    assert plan.notes == "aç karnına"


async def test_create_medication_plan_enables_medication_preference(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session)
    plan = await medication_service.create_medication_plan(
        db_session, user_id, "Metformin", 8, 0, "1,2,3,4,5"
    )

    pref = await preference_service.get_preference(db_session, plan.user_id, BotKey.MEDICATION)
    assert pref is not None
    assert pref.enabled is True


async def test_create_medication_plan_normalizes_with_food(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    plan = await medication_service.create_medication_plan(
        db_session, user_id, "Metformin", 8, 0, "1,2,3,4,5", with_food=" Empty "
    )

    assert plan.with_food == "empty"


async def test_create_medication_plan_rejects_empty_name(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)

    with pytest.raises(ValueError):
        await medication_service.create_medication_plan(db_session, user_id, "  ", 8, 0, "1,3,5")


async def test_create_medication_plan_rejects_invalid_hour(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)

    with pytest.raises(ValueError):
        await medication_service.create_medication_plan(
            db_session, user_id, "Metformin", 24, 0, "1,3,5"
        )


async def test_create_medication_plan_rejects_invalid_minute(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)

    with pytest.raises(ValueError):
        await medication_service.create_medication_plan(
            db_session, user_id, "Metformin", 8, 60, "1,3,5"
        )


async def test_create_medication_plan_rejects_invalid_with_food(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)

    with pytest.raises(ValueError):
        await medication_service.create_medication_plan(
            db_session, user_id, "Metformin", 8, 0, "1,3,5", with_food="breakfast"
        )


async def test_create_medication_plan_rejects_inverted_date_range(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session)

    with pytest.raises(ValueError):
        await medication_service.create_medication_plan(
            db_session,
            user_id,
            "Metformin",
            8,
            0,
            "1,3,5",
            start_date=date(2026, 8, 10),
            end_date=date(2026, 8, 1),
        )


async def test_create_medication_plan_rejects_long_notes(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)

    with pytest.raises(ValueError):
        await medication_service.create_medication_plan(
            db_session, user_id, "Metformin", 8, 0, "1,3,5", notes="x" * 501
        )


async def test_create_medication_plan_accepts_max_length_notes(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    plan = await medication_service.create_medication_plan(
        db_session, user_id, "Metformin", 8, 0, "1,3,5", notes="x" * 500
    )

    assert plan.notes == "x" * 500


async def test_list_medication_plans_ordered_by_time(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await medication_service.create_medication_plan(db_session, user_id, "İlaç A", 21, 0, "1,3,5")
    await medication_service.create_medication_plan(db_session, user_id, "İlaç B", 8, 30, "1,3,5")

    plans = await medication_service.list_medication_plans(db_session, user_id)

    assert [p.name for p in plans] == ["İlaç B", "İlaç A"]


async def test_list_medication_plans_active_only(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    plan = await medication_service.create_medication_plan(
        db_session, user_id, "İlaç A", 8, 0, "1,3,5"
    )
    await medication_service.create_medication_plan(db_session, user_id, "İlaç B", 9, 0, "1,3,5")
    await medication_service.toggle_medication_plan(db_session, plan.id, False)

    active = await medication_service.list_medication_plans(db_session, user_id, active_only=True)
    all_plans = await medication_service.list_medication_plans(db_session, user_id)

    assert [p.name for p in active] == ["İlaç B"]
    assert len(all_plans) == 2


async def test_get_medication_plan(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    plan = await medication_service.create_medication_plan(
        db_session, user_id, "Metformin", 8, 0, "1,3,5"
    )

    found = await medication_service.get_medication_plan(db_session, plan.id)

    assert found is not None
    assert found.id == plan.id


async def test_get_medication_plan_missing_returns_none(db_session: AsyncSession) -> None:
    found = await medication_service.get_medication_plan(db_session, 99999)
    assert found is None


async def test_update_medication_plan_partial(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    plan = await medication_service.create_medication_plan(
        db_session, user_id, "Metformin", 8, 0, "1,3,5", dose="500mg", notes="aç karnına"
    )

    updated = await medication_service.update_medication_plan(db_session, plan.id, dose="1000mg")

    assert updated.name == "Metformin"
    assert updated.dose == "1000mg"
    assert updated.target_hour == 8
    assert updated.notes == "aç karnına"


async def test_update_medication_plan_missing_raises(db_session: AsyncSession) -> None:
    with pytest.raises(ValueError):
        await medication_service.update_medication_plan(db_session, 99999, name="X")


async def test_update_medication_plan_rejects_inverted_date_range(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    plan = await medication_service.create_medication_plan(
        db_session, user_id, "Metformin", 8, 0, "1,3,5"
    )

    with pytest.raises(ValueError):
        await medication_service.update_medication_plan(
            db_session,
            plan.id,
            start_date=date(2026, 8, 10),
            end_date=date(2026, 8, 1),
        )


async def test_toggle_medication_plan(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    plan = await medication_service.create_medication_plan(
        db_session, user_id, "Metformin", 8, 0, "1,3,5"
    )

    updated = await medication_service.toggle_medication_plan(db_session, plan.id, False)

    assert updated.is_active is False


async def test_toggle_medication_plan_missing_raises(db_session: AsyncSession) -> None:
    with pytest.raises(ValueError):
        await medication_service.toggle_medication_plan(db_session, 99999, False)


async def test_generate_today_events_creates_for_matching_day(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    plan = await medication_service.create_medication_plan(
        db_session,
        user_id,
        "Metformin",
        9,
        0,
        "1",
        dose="500mg",
        notes="aç karnına",
    )

    events = await medication_service.generate_today_events(db_session, user_id, now=MONDAY_UTC)

    assert len(events) == 1
    event = events[0]
    assert event.bot_key == BotKey.MEDICATION.value
    assert event.related_type == "medication_plan"
    assert event.related_id == plan.id
    assert (
        event.scheduled_at.replace(tzinfo=UTC).astimezone(get_user_timezone("Europe/Istanbul")).hour
        == 9
    )
    assert '"name": "Metformin"' in event.interpretation_json
    assert '"dose": "500mg"' in event.interpretation_json
    assert '"with_food": "any"' in event.interpretation_json
    assert '"notes": "aç karnına"' in event.interpretation_json


async def test_generate_today_events_skips_non_matching_day(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await medication_service.create_medication_plan(db_session, user_id, "Metformin", 9, 0, "2")

    events = await medication_service.generate_today_events(db_session, user_id, now=MONDAY_UTC)

    assert events == []


async def test_generate_today_events_skips_inactive(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    plan = await medication_service.create_medication_plan(
        db_session, user_id, "Metformin", 9, 0, "1"
    )
    await medication_service.toggle_medication_plan(db_session, plan.id, False)

    events = await medication_service.generate_today_events(db_session, user_id, now=MONDAY_UTC)

    assert events == []


async def test_generate_today_events_skips_future_start_date(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await medication_service.create_medication_plan(
        db_session,
        user_id,
        "Metformin",
        9,
        0,
        "1",
        start_date=date(2026, 9, 1),
    )

    events = await medication_service.generate_today_events(db_session, user_id, now=MONDAY_UTC)

    assert events == []


async def test_generate_today_events_skips_past_end_date(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await medication_service.create_medication_plan(
        db_session,
        user_id,
        "Metformin",
        9,
        0,
        "1",
        end_date=date(2026, 7, 1),
    )

    events = await medication_service.generate_today_events(db_session, user_id, now=MONDAY_UTC)

    assert events == []


async def test_generate_today_events_is_idempotent(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await medication_service.create_medication_plan(db_session, user_id, "Metformin", 9, 0, "1")

    first = await medication_service.generate_today_events(db_session, user_id, now=MONDAY_UTC)
    second = await medication_service.generate_today_events(db_session, user_id, now=MONDAY_UTC)

    assert len(first) == 1
    assert len(second) == 1
    assert second[0].id == first[0].id


async def test_generate_today_events_scheduled_at_utc(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await medication_service.create_medication_plan(db_session, user_id, "Metformin", 12, 0, "1")

    events = await medication_service.generate_today_events(db_session, user_id, now=MONDAY_UTC)

    assert events[0].scheduled_at.replace(tzinfo=UTC) == datetime(2026, 8, 3, 9, 0, tzinfo=UTC)
