from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.timezone import get_user_timezone, now_in
from app.models import BotKey, ReminderEvent, ReminderStatus
from app.services import preference_service, sport_service, user_service
from tests.conftest import TELEGRAM_USER_ID


async def _user(db_session: AsyncSession) -> int:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    return user.id


async def test_create_and_list_sport_plans(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await sport_service.create_sport_plan(db_session, user_id, "Koşu", "1,3,5", 18, 30)

    plans = await sport_service.list_sport_plans(db_session, user_id)

    assert len(plans) == 1
    assert plans[0].sport_type == "Koşu"
    assert plans[0].target_hour == 18
    assert plans[0].target_minute == 30
    assert plans[0].days_of_week == "1,3,5"
    assert plans[0].is_active is True


async def test_create_sport_plan_enables_sport_preference(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    plan = await sport_service.create_sport_plan(db_session, user_id, "Yüzme", "1,2,3,4,5", 7, 0)

    pref = await preference_service.get_preference(db_session, plan.user_id, BotKey.SPORT)
    assert pref is not None
    assert pref.enabled is True


async def test_get_sport_plan(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    plan = await sport_service.create_sport_plan(db_session, user_id, "Koşu", "1,2,3,4,5", 18, 0)

    found = await sport_service.get_sport_plan(db_session, plan.id)

    assert found is not None
    assert found.id == plan.id


async def test_toggle_sport_plan(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    plan = await sport_service.create_sport_plan(db_session, user_id, "Koşu", "1,2,3,4,5", 18, 0)

    updated = await sport_service.toggle_sport_plan(db_session, plan.id, False)

    assert updated is not None
    assert updated.is_active is False


async def test_toggle_sport_plan_missing_returns_none(db_session: AsyncSession) -> None:
    updated = await sport_service.toggle_sport_plan(db_session, 99999, False)
    assert updated is None


async def test_generate_today_events_creates_for_matching_day(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    today = now_in()
    weekday = today.isoweekday()
    plan = await sport_service.create_sport_plan(db_session, user_id, "Koşu", str(weekday), 18, 30)

    events = await sport_service.generate_today_events(db_session, user_id, now=today)

    assert len(events) == 1
    event = events[0]
    assert event.bot_key == BotKey.SPORT.value
    assert event.related_type == "sport_plan"
    assert event.related_id == plan.id
    assert (
        event.scheduled_at.replace(tzinfo=UTC).astimezone(get_user_timezone(settings.timezone)).hour
        == 18
    )
    assert '"sport_type": "Koşu"' in event.interpretation_json


async def test_generate_today_events_uses_user_timezone(db_session: AsyncSession) -> None:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    user.timezone = "America/New_York"
    await db_session.commit()
    await sport_service.create_sport_plan(db_session, user.id, "Koşu", "6", 9, 0)
    fixed_now = datetime(2026, 8, 1, 23, 0, tzinfo=UTC)

    events = await sport_service.generate_today_events(db_session, user.id, now=fixed_now)

    assert len(events) == 1
    event = events[0]
    new_york = get_user_timezone("America/New_York")
    as_utc = event.scheduled_at.replace(tzinfo=UTC)
    assert as_utc.astimezone(new_york).hour == 9
    assert as_utc.hour == 13
    assert event.scheduled_local_date == datetime(2026, 8, 1, tzinfo=new_york).date()


async def test_generate_today_events_treats_naive_now_as_utc(db_session: AsyncSession) -> None:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    user.timezone = "America/New_York"
    await db_session.commit()
    await sport_service.create_sport_plan(db_session, user.id, "Koşu", "6", 9, 0)

    events = await sport_service.generate_today_events(
        db_session, user.id, now=datetime(2026, 8, 1, 23, 0)
    )

    assert len(events) == 1
    assert events[0].scheduled_at.replace(tzinfo=UTC).hour == 13


async def test_generate_today_events_uses_local_weekday(db_session: AsyncSession) -> None:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    user.timezone = "America/New_York"
    await db_session.commit()
    await sport_service.create_sport_plan(db_session, user.id, "Koşu", "7", 9, 0)
    fixed_now = datetime(2026, 8, 1, 23, 0, tzinfo=UTC)

    events = await sport_service.generate_today_events(db_session, user.id, now=fixed_now)

    assert events == []


async def test_generate_today_events_skips_non_matching_day(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    today = now_in()
    other_weekday = (today.isoweekday() % 7) + 1
    await sport_service.create_sport_plan(db_session, user_id, "Koşu", str(other_weekday), 18, 30)

    events = await sport_service.generate_today_events(db_session, user_id, now=today)

    assert events == []


async def test_generate_today_events_skips_inactive(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    today = now_in()
    weekday = today.isoweekday()
    plan = await sport_service.create_sport_plan(db_session, user_id, "Koşu", str(weekday), 18, 30)
    await sport_service.toggle_sport_plan(db_session, plan.id, False)

    events = await sport_service.generate_today_events(db_session, user_id, now=today)

    assert events == []


async def test_generate_today_events_is_idempotent(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    today = now_in()
    weekday = today.isoweekday()
    await sport_service.create_sport_plan(db_session, user_id, "Koşu", str(weekday), 18, 30)

    first = await sport_service.generate_today_events(db_session, user_id, now=today)
    second = await sport_service.generate_today_events(db_session, user_id, now=today)

    assert len(first) == 1
    assert len(second) == 1
    assert second[0].id == first[0].id


async def test_generate_today_events_for_all_only_active_users(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session)
    weekday = now_in().isoweekday()
    await sport_service.create_sport_plan(db_session, user_id, "Koşu", str(weekday), 18, 30)

    created = await sport_service.generate_today_events_for_all(db_session)

    assert created >= 1


async def test_completion_stats_counts_events(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    weekday = now_in().isoweekday()
    await sport_service.create_sport_plan(db_session, user_id, "Koşu", str(weekday), 18, 30)

    await sport_service.generate_today_events(db_session, user_id)
    stats = await sport_service.get_completion_stats(db_session, user_id, days=7)

    assert stats["total"] >= 1
    assert stats["completed"] == 0


async def test_completion_stats_counts_positive_status(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    weekday = now_in().isoweekday()
    await sport_service.create_sport_plan(db_session, user_id, "Koşu", str(weekday), 18, 30)
    events = await sport_service.generate_today_events(db_session, user_id)
    event = events[0]

    event.status = ReminderStatus.POSITIVE.value
    await db_session.commit()

    stats = await sport_service.get_completion_stats(db_session, user_id, days=7)

    assert stats["total"] >= 1
    assert stats["completed"] >= 1


async def test_sport_reminder_uses_sport_label() -> None:
    from app.services.event_labels import event_label

    event = ReminderEvent(
        user_id=1,
        bot_key=BotKey.SPORT.value,
        related_type="sport_plan",
        related_id=1,
        scheduled_at=datetime(2026, 8, 1, 18, 30),
        status=ReminderStatus.SCHEDULED.value,
        interpretation_json='{"sport_type": "Koşu"}',
        created_at=datetime(2026, 8, 1, 0, 0),
    )

    assert event_label(event) == "Koşu antrenmanı"
