from datetime import UTC, datetime, timedelta

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
from app.services import notification_service, user_service
from tests.conftest import TELEGRAM_USER_ID

_BOT = Bot(token="test")


async def _user(db_session: AsyncSession) -> int:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    return user.id


async def _event(db_session: AsyncSession, user_id: int) -> ReminderEvent:
    event = ReminderEvent(
        user_id=user_id,
        bot_key=BotKey.HABIT.value,
        related_type="habit",
        related_id=1,
        scheduled_at=datetime(2026, 8, 2, 8, 0, tzinfo=UTC),
        scheduled_local_date=datetime(2026, 8, 2, 8, 0, tzinfo=UTC).date(),
        dedupe_key="retry-flow-event",
        status=ReminderStatus.SCHEDULED.value,
        interpretation_json="{}",
        created_at=datetime(2026, 8, 2, 0, 0, tzinfo=UTC),
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


async def _ok_send(bot: object, event: ReminderEvent) -> str:
    return "12345"


async def _fail_send(bot: object, event: ReminderEvent) -> None:
    return None


async def test_flow_failed_to_sent(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    event = await _event(db_session, user_id)
    log = await _failed_log(db_session, user_id, event.id)

    first = await notification_service.retry_failed_notifications(db_session, _BOT, _fail_send)
    log.next_retry_at = now_in("UTC") - timedelta(minutes=1)
    await db_session.commit()
    second = await notification_service.retry_failed_notifications(db_session, _BOT, _ok_send)

    assert first == 1
    assert second == 1
    assert log.status == NotificationLogStatus.SENT.value
    assert log.retry_count == 1
    assert log.next_retry_at is None


async def test_flow_failed_to_abandoned_after_max_retries(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    event = await _event(db_session, user_id)
    log = await _failed_log(db_session, user_id, event.id)

    for _ in range(4):
        await notification_service.retry_failed_notifications(db_session, _BOT, _fail_send)
        if log.status == NotificationLogStatus.FAILED.value:
            log.next_retry_at = now_in("UTC") - timedelta(minutes=1)
            await db_session.commit()

    assert log.status == NotificationLogStatus.ABANDONED.value
    assert log.retry_count == 4
    assert log.next_retry_at is None

    again = await notification_service.retry_failed_notifications(db_session, _BOT, _ok_send)
    assert again == 0


async def test_flow_missing_event_abandoned(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    log = await _failed_log(db_session, user_id, None)

    processed = await notification_service.retry_failed_notifications(db_session, _BOT, _ok_send)

    assert processed == 1
    assert log.status == NotificationLogStatus.ABANDONED.value
