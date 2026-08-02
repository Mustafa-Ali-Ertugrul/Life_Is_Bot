from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
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
from app.scheduler.setup import setup_scheduler
from app.services import notification_service, user_service
from tests.conftest import TELEGRAM_USER_ID

_BOT = Bot(token="test")

_calls: list[str] = []


async def _ok_send(bot: object, chat_id: str, text: str) -> str:
    _calls.append(text)
    return "12345"


async def _reminder_fail_send(bot: object, event: ReminderEvent) -> None:
    return None


def _reset_calls() -> None:
    _calls.clear()


async def _user(db_session: AsyncSession) -> int:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    return user.id


async def _event(db_session: AsyncSession, user_id: int, bot_key: BotKey) -> ReminderEvent:
    event = ReminderEvent(
        user_id=user_id,
        bot_key=bot_key.value,
        related_type="habit",
        related_id=1,
        scheduled_at=datetime(2026, 8, 3, 8, 0, tzinfo=UTC),
        scheduled_local_date=datetime(2026, 8, 3, 8, 0, tzinfo=UTC).date(),
        dedupe_key=f"abandoned-flow-{bot_key.value}",
        status=ReminderStatus.SCHEDULED.value,
        interpretation_json="{}",
        created_at=datetime(2026, 8, 3, 0, 0, tzinfo=UTC),
    )
    db_session.add(event)
    await db_session.commit()
    return event


async def _failed_log(
    db_session: AsyncSession, user_id: int, event_id: int | None
) -> NotificationLog:
    log = NotificationLog(
        reminder_event_id=event_id,
        user_id=user_id,
        channel="telegram",
        message="reminder flow",
        status=NotificationLogStatus.FAILED.value,
        sent_at=now_in("UTC") - timedelta(minutes=10),
        retry_count=0,
        next_retry_at=now_in("UTC") - timedelta(minutes=1),
    )
    db_session.add(log)
    await db_session.commit()
    return log


async def test_flow_abandoned_then_notified(db_session: AsyncSession) -> None:
    _reset_calls()
    user_id = await _user(db_session)
    event = await _event(db_session, user_id, BotKey.HABIT)
    log = await _failed_log(db_session, user_id, event.id)

    for _ in range(4):
        await notification_service.retry_failed_notifications(db_session, _BOT, _reminder_fail_send)
        if log.status == NotificationLogStatus.FAILED.value:
            log.next_retry_at = now_in("UTC") - timedelta(minutes=1)
            await db_session.commit()

    assert log.status == NotificationLogStatus.ABANDONED.value

    notified = await notification_service.notify_abandoned(db_session, _BOT, _ok_send)

    assert notified == 1
    assert len(_calls) == 1
    assert log.abandoned_notified is True


async def test_flow_no_second_notification(db_session: AsyncSession) -> None:
    _reset_calls()
    user_id = await _user(db_session)
    event = await _event(db_session, user_id, BotKey.HABIT)
    log = await _failed_log(db_session, user_id, event.id)
    log.status = NotificationLogStatus.ABANDONED.value
    log.next_retry_at = None
    await db_session.commit()

    first = await notification_service.notify_abandoned(db_session, _BOT, _ok_send)
    second = await notification_service.notify_abandoned(db_session, _BOT, _ok_send)

    assert first == 1
    assert second == 0
    assert len(_calls) == 1


async def test_flow_multiple_bots_single_message(db_session: AsyncSession) -> None:
    _reset_calls()
    user_id = await _user(db_session)
    habit_event = await _event(db_session, user_id, BotKey.HABIT)
    med_event = await _event(db_session, user_id, BotKey.MEDICATION)
    for event in (habit_event, med_event):
        log = await _failed_log(db_session, user_id, event.id)
        log.status = NotificationLogStatus.ABANDONED.value
        log.next_retry_at = None
        await db_session.commit()

    notified = await notification_service.notify_abandoned(db_session, _BOT, _ok_send)

    assert notified == 1
    assert len(_calls) == 1
    assert "Rutin" in _calls[0]
    assert "İlaç" in _calls[0]


async def test_flow_missing_event_generic_message(db_session: AsyncSession) -> None:
    _reset_calls()
    user_id = await _user(db_session)
    event = await _event(db_session, user_id, BotKey.HABIT)
    log = await _failed_log(db_session, user_id, event.id)
    log.status = NotificationLogStatus.ABANDONED.value
    log.next_retry_at = None
    await db_session.commit()
    await db_session.execute(delete(ReminderEvent))
    await db_session.commit()

    notified = await notification_service.notify_abandoned(db_session, _BOT, _ok_send)

    assert notified == 1
    assert "hatırlatma" in _calls[0]
    assert log.abandoned_notified is True


async def test_scheduler_registers_abandoned_job() -> None:
    scheduler = setup_scheduler()
    try:
        job = scheduler.get_job("abandoned_notification")
        assert job is not None
        assert job.trigger.interval.total_seconds() == 1800
    finally:
        from app.scheduler.engine import stop_scheduler

        stop_scheduler()
