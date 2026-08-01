from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.notification_policy import evaluate_notification
from app.core.timezone import now_in
from app.models import BotKey, ResponseType, User
from app.services import preference_service, reminder_service, response_service

IST = ZoneInfo("Europe/Istanbul")


async def _user(
    db_session: AsyncSession,
    *,
    is_active: bool = True,
    consent_given: bool = True,
    notifications_enabled: bool = True,
    quiet_hours_enabled: bool = False,
    quiet_hours_start: str | None = None,
    quiet_hours_end: str | None = None,
) -> User:
    user = User(
        name="Test",
        timezone="Europe/Istanbul",
        language="tr",
        consent_given=consent_given,
        is_active=is_active,
        notifications_enabled=notifications_enabled,
        quiet_hours_enabled=quiet_hours_enabled,
        quiet_hours_start=quiet_hours_start,
        quiet_hours_end=quiet_hours_end,
        week_start_day=1,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _event_id(
    db_session: AsyncSession,
    user_id: int,
    bot_key: BotKey = BotKey.HABIT,
) -> int:
    await reminder_service.create_event(
        db_session,
        user_id=user_id,
        bot_key=bot_key,
        scheduled_at=now_in() - timedelta(minutes=5),
        related_type="habit",
        related_id=1,
    )
    due = await reminder_service.find_due_events(db_session, now_in())
    return due[0].id


async def test_policy_suppresses_when_user_inactive(db_session: AsyncSession) -> None:
    user = await _user(db_session, is_active=False)
    event_id = await _event_id(db_session, user.id)
    event = await reminder_service.get_event(db_session, event_id)
    assert event is not None

    decision = await evaluate_notification(db_session, user, event, now_in())

    assert decision["action"] == "suppress"
    assert decision["reason"] == "user_inactive"


async def test_policy_suppresses_when_consent_missing(db_session: AsyncSession) -> None:
    user = await _user(db_session, consent_given=False)
    event_id = await _event_id(db_session, user.id)
    event = await reminder_service.get_event(db_session, event_id)
    assert event is not None

    decision = await evaluate_notification(db_session, user, event, now_in())

    assert decision["action"] == "suppress"
    assert decision["reason"] == "consent_missing"


async def test_policy_suppresses_when_notifications_disabled(db_session: AsyncSession) -> None:
    user = await _user(db_session, notifications_enabled=False)
    event_id = await _event_id(db_session, user.id)
    event = await reminder_service.get_event(db_session, event_id)
    assert event is not None

    decision = await evaluate_notification(db_session, user, event, now_in())

    assert decision["action"] == "suppress"
    assert decision["reason"] == "notifications_disabled"


async def test_policy_suppresses_when_bot_preference_disabled(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    event_id = await _event_id(db_session, user.id, bot_key=BotKey.SPORT)
    event = await reminder_service.get_event(db_session, event_id)
    assert event is not None
    await preference_service.toggle_preference(db_session, user.id, BotKey.SPORT, enabled=False)

    decision = await evaluate_notification(db_session, user, event, now_in())

    assert decision["action"] == "suppress"
    assert decision["reason"] == "bot_disabled"


async def test_policy_suppresses_when_no_preference_non_core(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    event_id = await _event_id(db_session, user.id, bot_key=BotKey.SPORT)
    event = await reminder_service.get_event(db_session, event_id)
    assert event is not None

    decision = await evaluate_notification(db_session, user, event, now_in())

    assert decision["action"] == "suppress"
    assert decision["reason"] == "bot_disabled"


async def test_policy_sends_for_core_without_preference(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    event_id = await _event_id(db_session, user.id, bot_key=BotKey.CORE)
    event = await reminder_service.get_event(db_session, event_id)
    assert event is not None

    decision = await evaluate_notification(db_session, user, event, now_in())

    assert decision["action"] == "send_now"


async def test_policy_defers_during_quiet_hours(db_session: AsyncSession) -> None:
    user = await _user(
        db_session,
        quiet_hours_enabled=True,
        quiet_hours_start="23:00",
        quiet_hours_end="07:00",
    )
    event_id = await _event_id(db_session, user.id, bot_key=BotKey.CORE)
    event = await reminder_service.get_event(db_session, event_id)
    assert event is not None
    now = datetime(2026, 8, 1, 23, 30, tzinfo=IST)

    decision = await evaluate_notification(db_session, user, event, now)

    assert decision["action"] == "defer"
    assert decision["reason"] == "quiet_hours"
    assert decision["defer_until"] is not None
    assert decision["defer_until"] > now
    assert decision["defer_until"].astimezone(IST).hour == 7


async def test_policy_defer_until_is_utc(db_session: AsyncSession) -> None:
    """Deferred notify time must be canonicalized to UTC (tracks #29)."""
    user = await _user(
        db_session,
        quiet_hours_enabled=True,
        quiet_hours_start="23:00",
        quiet_hours_end="07:00",
    )
    event_id = await _event_id(db_session, user.id, bot_key=BotKey.CORE)
    event = await reminder_service.get_event(db_session, event_id)
    assert event is not None
    now = datetime(2026, 8, 1, 23, 30, tzinfo=IST)

    decision = await evaluate_notification(db_session, user, event, now)

    assert decision["action"] == "defer"
    assert decision["defer_until"] is not None
    assert decision["defer_until"].tzinfo is not None
    assert decision["defer_until"].utcoffset() == timedelta(0)
    assert decision["defer_until"].tzinfo == UTC


async def test_policy_sends_outside_quiet_hours(db_session: AsyncSession) -> None:
    user = await _user(
        db_session,
        quiet_hours_enabled=True,
        quiet_hours_start="23:00",
        quiet_hours_end="07:00",
    )
    event_id = await _event_id(db_session, user.id, bot_key=BotKey.CORE)
    event = await reminder_service.get_event(db_session, event_id)
    assert event is not None
    now = datetime(2026, 8, 1, 12, 0, tzinfo=IST)

    decision = await evaluate_notification(db_session, user, event, now)

    assert decision["action"] == "send_now"


async def test_policy_suppresses_after_response(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    event_id = await _event_id(db_session, user.id, bot_key=BotKey.CORE)
    event = await reminder_service.get_event(db_session, event_id)
    assert event is not None
    await response_service.save_response(
        db_session, event_id, user.id, BotKey.HABIT, ResponseType.DONE
    )

    decision = await evaluate_notification(db_session, user, event, now_in())

    assert decision["action"] == "suppress"
    assert decision["reason"] == "not_scheduled"
