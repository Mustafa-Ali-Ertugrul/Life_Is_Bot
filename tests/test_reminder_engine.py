from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone import now_in
from app.models import BotKey, ReminderEvent, ResponseType
from app.services import preference_service, reminder_service, response_service, user_service
from tests.conftest import TELEGRAM_USER_ID


async def _user(db_session: AsyncSession) -> int:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    return user.id


async def _event(
    db_session: AsyncSession,
    user_id: int,
    *,
    bot_key: BotKey = BotKey.HABIT,
    when: datetime | None = None,
    related_type: str = "habit",
    related_id: int = 1,
) -> ReminderEvent:
    return await reminder_service.create_event(
        db_session,
        user_id=user_id,
        bot_key=bot_key,
        scheduled_at=when or (now_in() - timedelta(minutes=5)),
        related_type=related_type,
        related_id=related_id,
    )


async def test_create_event_prevents_duplicate_same_day(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    when = now_in().replace(hour=9, minute=0, second=0, microsecond=0)

    first = await _event(db_session, user_id, when=when)
    second = await _event(db_session, user_id, when=when + timedelta(minutes=30))

    assert second.id == first.id


async def test_create_event_allows_duplicate_different_day(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    today = now_in().replace(hour=9, minute=0, second=0, microsecond=0)

    first = await _event(db_session, user_id, when=today)
    second = await _event(db_session, user_id, when=today + timedelta(days=1))

    assert second.id != first.id


async def test_find_due_events_returns_scheduled_unnotified(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _event(db_session, user_id)
    await _event(db_session, user_id, related_type="sport", related_id=2)

    due = await reminder_service.find_due_events(db_session, now_in())

    assert len(due) == 2


async def test_find_due_events_excludes_future(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _event(db_session, user_id, when=now_in() + timedelta(hours=1))

    due = await reminder_service.find_due_events(db_session, now_in())

    assert due == []


async def test_find_due_events_excludes_notified(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    event = await _event(db_session, user_id)
    await reminder_service.mark_notified(db_session, event.id)

    due = await reminder_service.find_due_events(db_session, now_in())

    assert due == []


async def test_mark_notified_sets_status_and_notified_at(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    event = await _event(db_session, user_id)

    ok = await reminder_service.mark_notified(db_session, event.id)

    assert ok is True
    updated = await reminder_service.get_event(db_session, event.id)
    assert updated is not None
    assert updated.status == "notified"
    assert updated.notified_at is not None


async def test_mark_notified_idempotent(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    event = await _event(db_session, user_id)

    first = await reminder_service.mark_notified(db_session, event.id)
    second = await reminder_service.mark_notified(db_session, event.id)

    assert first is True
    assert second is False


async def test_should_skip_notify_when_preference_disabled(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    event = await _event(db_session, user_id, bot_key=BotKey.SPORT)
    await preference_service.get_or_create_preference(db_session, user_id, BotKey.SPORT)

    skip = await reminder_service.should_skip_notify(db_session, event)

    assert skip is True


async def test_should_skip_notify_when_preference_enabled(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    event = await _event(db_session, user_id, bot_key=BotKey.SPORT)
    await preference_service.toggle_preference(db_session, user_id, BotKey.SPORT, enabled=True)

    skip = await reminder_service.should_skip_notify(db_session, event)

    assert skip is False


async def test_should_skip_notify_after_response(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    event = await _event(db_session, user_id)
    await preference_service.toggle_preference(db_session, user_id, BotKey.HABIT, enabled=True)
    await response_service.save_response(
        db_session, event.id, user_id, BotKey.HABIT, ResponseType.DONE
    )

    skip = await reminder_service.should_skip_notify(db_session, event)

    assert skip is True


async def test_snooze_creates_new_event(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    event = await _event(db_session, user_id, bot_key=BotKey.MEDICATION, related_type="medication")
    now = now_in()

    await response_service.save_response(
        db_session, event.id, user_id, BotKey.MEDICATION, ResponseType.SNOOZED
    )
    new_event = await reminder_service.create_event(
        db_session,
        user_id=user_id,
        bot_key=BotKey.MEDICATION,
        scheduled_at=now + timedelta(minutes=10),
        related_type="medication",
        related_id=1,
    )

    assert new_event.id != event.id
    scheduled = new_event.scheduled_at.replace(tzinfo=now.tzinfo)
    assert scheduled >= now + timedelta(minutes=9)
