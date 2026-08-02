from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Bot

from app.core.timezone import now_in
from app.models import (
    BotKey,
    NotificationLog,
    NotificationLogStatus,
    ReminderEvent,
    ReminderStatus,
)
from app.scheduler import engine, jobs
from app.services import notification_service, preference_service, reminder_service, user_service
from tests.conftest import TELEGRAM_USER_ID

_BOT = Bot(token="test")

_calls: list[str] = []


async def _ok_send(bot: object, chat_id: str, text: str) -> str:
    _calls.append(text)
    return "12345"


async def _reminder_send(bot: object, event: ReminderEvent) -> str:
    _calls.append(f"send:{event.bot_key}")
    return "12345"


def _reset_calls() -> None:
    _calls.clear()


async def _user(db_session: AsyncSession) -> int:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    if not user.consent_given:
        user.consent_given = True
        await db_session.commit()
    return user.id


async def _enable(db_session: AsyncSession, user_id: int, bot_key: BotKey) -> None:
    await preference_service.toggle_preference(db_session, user_id, bot_key, enabled=True)


async def _event(
    db_session: AsyncSession,
    user_id: int,
    bot_key: BotKey,
    *,
    related_id: int = 1,
) -> ReminderEvent:
    return await reminder_service.create_event(
        db_session,
        user_id=user_id,
        bot_key=bot_key,
        scheduled_at=now_in("UTC") - timedelta(minutes=5),
        related_type="habit",
        related_id=related_id,
    )


async def _logs(db_session: AsyncSession) -> list[NotificationLog]:
    result = await db_session.execute(select(NotificationLog))
    return list(result.scalars().all())


async def _fake_send_reminder(bot: object, event: ReminderEvent) -> str | None:
    _calls.append(f"send:{event.bot_key}")
    return "12345"


@pytest.fixture
def tick_patch(monkeypatch: pytest.MonkeyPatch, db_session: AsyncSession) -> None:
    monkeypatch.setattr(jobs, "async_session_factory", lambda: db_session)
    monkeypatch.setattr(jobs, "send_reminder", _fake_send_reminder)
    monkeypatch.setattr(engine, "get_bot", lambda: _BOT)


async def test_flow_digest_full_cycle(tick_patch: None, db_session: AsyncSession) -> None:
    _reset_calls()
    user_id = await _user(db_session)
    await _enable(db_session, user_id, BotKey.HABIT)
    event = await _event(db_session, user_id, BotKey.HABIT)
    event_id = event.id

    await jobs.reminder_tick()

    logs = await _logs(db_session)
    assert len(logs) == 1
    assert logs[0].status == NotificationLogStatus.DIGEST_PENDING.value

    notified = await notification_service.send_digest(db_session, _BOT, _ok_send)

    assert notified == 1
    assert len(_calls) == 1
    assert "📋 Son hatırlatmalarınız" in _calls[0]
    logs = await _logs(db_session)
    assert logs[0].status == NotificationLogStatus.SENT.value
    fresh = await db_session.get(ReminderEvent, event_id)
    assert fresh is not None and fresh.status == ReminderStatus.NOTIFIED.value


async def test_flow_medication_never_queued(tick_patch: None, db_session: AsyncSession) -> None:
    _reset_calls()
    user_id = await _user(db_session)
    await _enable(db_session, user_id, BotKey.MEDICATION)
    event = await _event(db_session, user_id, BotKey.MEDICATION)
    event_id = event.id

    await jobs.reminder_tick()

    assert _calls == ["send:medication_bot"]
    logs = await _logs(db_session)
    assert logs[0].status == NotificationLogStatus.SENT.value
    assert all(log.status != NotificationLogStatus.DIGEST_PENDING.value for log in logs)
    fresh = await db_session.get(ReminderEvent, event_id)
    assert fresh is not None and fresh.status == ReminderStatus.NOTIFIED.value


async def test_flow_three_bots_single_digest(tick_patch: None, db_session: AsyncSession) -> None:
    _reset_calls()
    user_id = await _user(db_session)
    await _enable(db_session, user_id, BotKey.HABIT)
    await _enable(db_session, user_id, BotKey.SPORT)
    await _enable(db_session, user_id, BotKey.SUPPLEMENT)
    await _event(db_session, user_id, BotKey.HABIT, related_id=1)
    await _event(db_session, user_id, BotKey.SPORT, related_id=2)
    await _event(db_session, user_id, BotKey.SUPPLEMENT, related_id=3)

    await jobs.reminder_tick()
    notified = await notification_service.send_digest(db_session, _BOT, _ok_send)

    assert notified == 1
    assert len(_calls) == 1
    assert "Rutin" in _calls[0]
    assert "Spor" in _calls[0]
    assert "Supplement" in _calls[0]
    logs = await _logs(db_session)
    assert all(log.status == NotificationLogStatus.SENT.value for log in logs)


async def test_flow_quiet_hours_delays_until_next_job(
    monkeypatch: pytest.MonkeyPatch, tick_patch: None, db_session: AsyncSession
) -> None:
    _reset_calls()
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    if not user.consent_given:
        user.consent_given = True
    user.quiet_hours_enabled = True
    user.quiet_hours_start = "23:00"
    user.quiet_hours_end = "07:00"
    await db_session.commit()
    await _enable(db_session, user.id, BotKey.HABIT)

    day_now = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(jobs, "now_in", lambda *args: day_now)
    monkeypatch.setattr("tests.test_digest_flow.now_in", lambda *args: day_now)
    await _event(db_session, user.id, BotKey.HABIT)

    await jobs.reminder_tick()
    logs = await _logs(db_session)
    assert logs[0].status == NotificationLogStatus.DIGEST_PENDING.value

    quiet_now = datetime(2026, 8, 2, 1, 0, tzinfo=UTC)
    monkeypatch.setattr(notification_service, "now_in", lambda *args: quiet_now)
    first = await notification_service.send_digest(db_session, _BOT, _ok_send)
    assert first == 0
    assert _calls == []

    day_now = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(notification_service, "now_in", lambda *args: day_now)
    second = await notification_service.send_digest(db_session, _BOT, _ok_send)
    assert second == 1
    assert len(_calls) == 1


async def test_flow_digest_failure_retried_individually(
    tick_patch: None, db_session: AsyncSession
) -> None:
    _reset_calls()
    user_id = await _user(db_session)
    await _enable(db_session, user_id, BotKey.HABIT)
    await _event(db_session, user_id, BotKey.HABIT)

    await jobs.reminder_tick()

    async def _fail_send(bot: object, chat_id: str, text: str) -> None:
        return None

    notified = await notification_service.send_digest(db_session, _BOT, _fail_send)
    assert notified == 0
    logs = await _logs(db_session)
    assert logs[0].status == NotificationLogStatus.FAILED.value
    assert logs[0].next_retry_at is not None

    logs[0].next_retry_at = now_in("UTC") - timedelta(minutes=1)
    await db_session.commit()

    _reset_calls()
    processed = await notification_service.retry_failed_notifications(
        db_session, _BOT, _reminder_send
    )

    assert processed == 1
    assert _calls == ["send:habit_bot"]
    logs = await _logs(db_session)
    assert logs[0].status == NotificationLogStatus.SENT.value


async def test_flow_no_duplicate_queues(tick_patch: None, db_session: AsyncSession) -> None:
    _reset_calls()
    user_id = await _user(db_session)
    await _enable(db_session, user_id, BotKey.HABIT)
    await _event(db_session, user_id, BotKey.HABIT)

    await jobs.reminder_tick()
    await jobs.reminder_tick()

    logs = await _logs(db_session)
    assert len(logs) == 1
    assert logs[0].status == NotificationLogStatus.DIGEST_PENDING.value
