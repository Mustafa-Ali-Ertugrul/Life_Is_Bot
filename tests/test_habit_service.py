from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone import now_in
from app.models import BotKey, ReminderEvent, ReminderStatus
from app.services import habit_service, user_service
from tests.conftest import TELEGRAM_USER_ID


async def _user(db_session: AsyncSession) -> int:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    return user.id


async def test_parse_days() -> None:
    assert habit_service.parse_days("1,3,5") == {1, 3, 5}
    assert habit_service.parse_days("1,2,3,4,5,6,7") == {1, 2, 3, 4, 5, 6, 7}
    assert habit_service.parse_days(" 1 , 7 ") == {1, 7}
    assert habit_service.parse_days("x,2") == {2}
    assert habit_service.parse_days("") == set()


async def test_create_and_list_habits(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await habit_service.create_habit(db_session, user_id, "Sabah sporu", 8, 30, "1,2,3,4,5")

    habits = await habit_service.list_habits(db_session, user_id)

    assert len(habits) == 1
    assert habits[0].name == "Sabah sporu"
    assert habits[0].target_hour == 8
    assert habits[0].target_minute == 30
    assert habits[0].days_of_week == "1,2,3,4,5"
    assert habits[0].is_active is True


async def test_toggle_habit(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    habit = await habit_service.create_habit(db_session, user_id, "Su iç", 9, 0, "1,2,3,4,5,6,7")

    updated = await habit_service.toggle_habit(db_session, habit.id, False)

    assert updated is not None
    assert updated.is_active is False


async def test_toggle_habit_missing_returns_none(db_session: AsyncSession) -> None:
    updated = await habit_service.toggle_habit(db_session, 99999, False)
    assert updated is None


async def test_generate_today_events_creates_for_matching_day(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    today = now_in()
    weekday = today.isoweekday()
    habit = await habit_service.create_habit(
        db_session, user_id, "Sabah sporu", 8, 30, str(weekday)
    )

    events = await habit_service.generate_today_events(db_session, user_id, now=today)

    assert len(events) == 1
    event = events[0]
    assert event.bot_key == BotKey.HABIT.value
    assert event.related_type == "habit"
    assert event.related_id == habit.id
    assert event.scheduled_at.replace(tzinfo=today.tzinfo).hour == 8
    assert "Sabah sporu" in event.interpretation_json


async def test_generate_today_events_skips_non_matching_day(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    today = now_in()
    other_weekday = (today.isoweekday() % 7) + 1
    await habit_service.create_habit(db_session, user_id, "Sabah sporu", 8, 30, str(other_weekday))

    events = await habit_service.generate_today_events(db_session, user_id, now=today)

    assert events == []


async def test_generate_today_events_skips_inactive(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    today = now_in()
    weekday = today.isoweekday()
    habit = await habit_service.create_habit(
        db_session, user_id, "Sabah sporu", 8, 30, str(weekday)
    )
    await habit_service.toggle_habit(db_session, habit.id, False)

    events = await habit_service.generate_today_events(db_session, user_id, now=today)

    assert events == []


async def test_generate_today_events_is_idempotent(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    today = now_in()
    weekday = today.isoweekday()
    await habit_service.create_habit(db_session, user_id, "Sabah sporu", 8, 30, str(weekday))

    first = await habit_service.generate_today_events(db_session, user_id, now=today)
    second = await habit_service.generate_today_events(db_session, user_id, now=today)

    assert len(first) == 1
    assert len(second) == 1
    assert second[0].id == first[0].id


async def test_generate_today_events_for_all_only_active_users(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session)
    weekday = now_in().isoweekday()
    await habit_service.create_habit(db_session, user_id, "Sabah sporu", 8, 30, str(weekday))

    created = await habit_service.generate_today_events_for_all(db_session)

    assert created >= 1


async def test_completion_stats_counts_events(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    weekday = now_in().isoweekday()
    await habit_service.create_habit(db_session, user_id, "Sabah sporu", 8, 30, str(weekday))

    await habit_service.generate_today_events(db_session, user_id)
    stats = await habit_service.get_completion_stats(db_session, user_id, days=7)

    assert stats["total"] >= 1
    assert stats["completed"] == 0


async def test_completion_stats_counts_positive_status(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    weekday = now_in().isoweekday()
    await habit_service.create_habit(db_session, user_id, "Sabah sporu", 8, 30, str(weekday))
    events = await habit_service.generate_today_events(db_session, user_id)
    event = events[0]

    event.status = ReminderStatus.POSITIVE.value
    await db_session.commit()

    stats = await habit_service.get_completion_stats(db_session, user_id, days=7)

    assert stats["total"] >= 1
    assert stats["completed"] >= 1


async def test_habit_reminder_uses_habit_label() -> None:
    from app.services.event_labels import event_label

    event = ReminderEvent(
        user_id=1,
        bot_key=BotKey.HABIT.value,
        related_type="habit",
        related_id=1,
        scheduled_at=datetime(2026, 8, 1, 8, 30),
        status=ReminderStatus.SCHEDULED.value,
        interpretation_json='{"habit_name": "Sabah sporu"}',
        created_at=datetime(2026, 8, 1, 0, 0),
    )

    assert event_label(event) == "Sabah sporu"
