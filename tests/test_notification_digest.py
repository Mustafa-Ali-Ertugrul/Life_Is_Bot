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
from app.services.notification_service import _format_digest
from tests.conftest import TELEGRAM_USER_ID

_BOT = Bot(token="test")

_calls: list[str] = []


async def _ok_send(bot: object, chat_id: str, text: str) -> str:
    _calls.append(text)
    return "12345"


async def _fail_send(bot: object, chat_id: str, text: str) -> None:
    return None


def _reset_calls() -> None:
    _calls.clear()


async def _user(db_session: AsyncSession, telegram_id: str = TELEGRAM_USER_ID) -> int:
    user = await user_service.find_or_create_by_telegram_id(db_session, telegram_id)
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
    interpretation_json: str = "{}",
) -> ReminderEvent:
    return await reminder_service.create_event(
        db_session,
        user_id=user_id,
        bot_key=bot_key,
        scheduled_at=now_in("UTC") - timedelta(minutes=5),
        related_type="habit",
        related_id=related_id,
        interpretation_json=interpretation_json,
    )


async def _digest_log(
    db_session: AsyncSession, user_id: int, event_id: int | None
) -> NotificationLog:
    log = NotificationLog(
        reminder_event_id=event_id,
        user_id=user_id,
        channel="telegram",
        message="reminder test",
        status=NotificationLogStatus.DIGEST_PENDING.value,
        sent_at=now_in("UTC"),
        retry_count=0,
    )
    db_session.add(log)
    await db_session.commit()
    return log


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


async def test_tick_medication_instant(tick_patch: None, db_session: AsyncSession) -> None:
    _reset_calls()
    user_id = await _user(db_session)
    await _enable(db_session, user_id, BotKey.MEDICATION)
    event = await _event(db_session, user_id, BotKey.MEDICATION)
    event_id = event.id

    await jobs.reminder_tick()

    assert _calls == ["send:medication_bot"]
    logs = await _logs(db_session)
    assert len(logs) == 1
    assert logs[0].status == NotificationLogStatus.SENT.value
    fresh = await db_session.get(ReminderEvent, event_id)
    assert fresh is not None and fresh.status == ReminderStatus.NOTIFIED.value


async def test_tick_core_instant(tick_patch: None, db_session: AsyncSession) -> None:
    _reset_calls()
    user_id = await _user(db_session)
    await _event(db_session, user_id, BotKey.CORE)

    await jobs.reminder_tick()

    assert _calls == ["send:core_bot"]
    logs = await _logs(db_session)
    assert len(logs) == 1
    assert logs[0].status == NotificationLogStatus.SENT.value


async def test_tick_assessment_instant(tick_patch: None, db_session: AsyncSession) -> None:
    _reset_calls()
    user_id = await _user(db_session)
    await _enable(db_session, user_id, BotKey.ASSESSMENT)
    await _event(db_session, user_id, BotKey.ASSESSMENT)

    await jobs.reminder_tick()

    assert _calls == ["send:assessment_bot"]
    logs = await _logs(db_session)
    assert logs[0].status == NotificationLogStatus.SENT.value


async def test_tick_habit_queues_digest(tick_patch: None, db_session: AsyncSession) -> None:
    _reset_calls()
    user_id = await _user(db_session)
    await _enable(db_session, user_id, BotKey.HABIT)
    event = await _event(db_session, user_id, BotKey.HABIT)
    event_id = event.id

    await jobs.reminder_tick()

    assert _calls == []
    logs = await _logs(db_session)
    assert len(logs) == 1
    assert logs[0].status == NotificationLogStatus.DIGEST_PENDING.value
    fresh = await db_session.get(ReminderEvent, event_id)
    assert fresh is not None and fresh.status == ReminderStatus.NOTIFIED.value


async def test_tick_sport_queues_digest(tick_patch: None, db_session: AsyncSession) -> None:
    _reset_calls()
    user_id = await _user(db_session)
    await _enable(db_session, user_id, BotKey.SPORT)
    await _event(db_session, user_id, BotKey.SPORT)

    await jobs.reminder_tick()

    assert _calls == []
    logs = await _logs(db_session)
    assert logs[0].status == NotificationLogStatus.DIGEST_PENDING.value


async def test_tick_supplement_queues_digest(tick_patch: None, db_session: AsyncSession) -> None:
    _reset_calls()
    user_id = await _user(db_session)
    await _enable(db_session, user_id, BotKey.SUPPLEMENT)
    await _event(db_session, user_id, BotKey.SUPPLEMENT)

    await jobs.reminder_tick()

    assert _calls == []
    logs = await _logs(db_session)
    assert logs[0].status == NotificationLogStatus.DIGEST_PENDING.value


async def test_tick_step_queues_digest(tick_patch: None, db_session: AsyncSession) -> None:
    _reset_calls()
    user_id = await _user(db_session)
    await _enable(db_session, user_id, BotKey.STEP)
    await _event(db_session, user_id, BotKey.STEP)

    await jobs.reminder_tick()

    assert _calls == []
    logs = await _logs(db_session)
    assert logs[0].status == NotificationLogStatus.DIGEST_PENDING.value


async def test_send_digest_no_pending(db_session: AsyncSession) -> None:
    _reset_calls()
    notified = await notification_service.send_digest(db_session, _BOT, _ok_send)

    assert notified == 0
    assert _calls == []


async def test_send_digest_single_user_two_logs(db_session: AsyncSession) -> None:
    _reset_calls()
    user_id = await _user(db_session)
    e1 = await _event(db_session, user_id, BotKey.HABIT, related_id=1)
    e2 = await _event(db_session, user_id, BotKey.SPORT, related_id=2)
    await _digest_log(db_session, user_id, e1.id)
    await _digest_log(db_session, user_id, e2.id)

    notified = await notification_service.send_digest(db_session, _BOT, _ok_send)

    assert notified == 1
    assert len(_calls) == 1
    logs = await _logs(db_session)
    assert all(log.status == NotificationLogStatus.SENT.value for log in logs)
    assert logs[0].sent_at is not None


async def test_send_digest_two_users_two_messages(db_session: AsyncSession) -> None:
    _reset_calls()
    u1 = await _user(db_session)
    u2 = await _user(db_session, telegram_id=str(int(TELEGRAM_USER_ID) + 1))
    e1 = await _event(db_session, u1, BotKey.HABIT)
    e2 = await _event(db_session, u2, BotKey.STEP)
    await _digest_log(db_session, u1, e1.id)
    await _digest_log(db_session, u2, e2.id)

    notified = await notification_service.send_digest(db_session, _BOT, _ok_send)

    assert notified == 2
    assert len(_calls) == 2


async def test_send_digest_skips_quiet_hours(
    monkeypatch: pytest.MonkeyPatch, db_session: AsyncSession
) -> None:
    _reset_calls()
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    user.quiet_hours_enabled = True
    user.quiet_hours_start = "23:00"
    user.quiet_hours_end = "07:00"
    await db_session.commit()
    event = await _event(db_session, user.id, BotKey.HABIT)
    log = await _digest_log(db_session, user.id, event.id)

    fixed_now = datetime(2026, 8, 2, 1, 0, tzinfo=UTC)
    monkeypatch.setattr(notification_service, "now_in", lambda *args: fixed_now)

    notified = await notification_service.send_digest(db_session, _BOT, _ok_send)

    assert notified == 0
    assert _calls == []
    assert log.status == NotificationLogStatus.DIGEST_PENDING.value


async def test_send_digest_send_failure_marks_failed(db_session: AsyncSession) -> None:
    _reset_calls()
    user_id = await _user(db_session)
    event = await _event(db_session, user_id, BotKey.HABIT)
    log = await _digest_log(db_session, user_id, event.id)

    notified = await notification_service.send_digest(db_session, _BOT, _fail_send)

    assert notified == 0
    assert log.status == NotificationLogStatus.FAILED.value
    assert log.next_retry_at is not None


async def test_format_digest_labels(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    e1 = await _event(
        db_session,
        user_id,
        BotKey.HABIT,
        related_id=1,
        interpretation_json='{"habit_name": "Sabah sporu"}',
    )
    e2 = await _event(db_session, user_id, BotKey.SPORT, related_id=2)
    log1 = await _digest_log(db_session, user_id, e1.id)
    log2 = await _digest_log(db_session, user_id, e2.id)

    text = await _format_digest(db_session, [log1, log2])

    assert text is not None
    assert text.startswith("📋 Son hatırlatmalarınız")
    assert "• Rutin: Sabah sporu" in text
    assert "• Spor: habit" in text


async def test_retry_ignores_digest_pending(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    e1 = await _event(db_session, user_id, BotKey.HABIT, related_id=1)
    e2 = await _event(db_session, user_id, BotKey.SPORT, related_id=2)
    failed = NotificationLog(
        reminder_event_id=e1.id,
        user_id=user_id,
        channel="telegram",
        message="reminder test",
        status=NotificationLogStatus.FAILED.value,
        sent_at=now_in("UTC"),
        retry_count=0,
        next_retry_at=now_in("UTC") - timedelta(minutes=1),
    )
    db_session.add(failed)
    await db_session.commit()
    pending = await _digest_log(db_session, user_id, e2.id)

    async def _ok_reminder_send(bot: object, event: ReminderEvent) -> str:
        return "12345"

    processed = await notification_service.retry_failed_notifications(
        db_session, _BOT, _ok_reminder_send
    )

    assert processed == 1
    assert failed.status == NotificationLogStatus.SENT.value
    assert pending.status == NotificationLogStatus.DIGEST_PENDING.value
