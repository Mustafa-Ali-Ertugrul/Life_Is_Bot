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
from app.services.notification_service import _compute_next_retry
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
        dedupe_key="retry-test-event",
        status=ReminderStatus.SCHEDULED.value,
        interpretation_json="{}",
        created_at=datetime(2026, 8, 2, 0, 0, tzinfo=UTC),
    )
    db_session.add(event)
    await db_session.commit()
    return event


async def _failed_log(
    db_session: AsyncSession,
    user_id: int,
    event_id: int | None,
    *,
    retry_count: int = 0,
    next_retry_at: datetime | None = None,
) -> NotificationLog:
    log = NotificationLog(
        reminder_event_id=event_id,
        user_id=user_id,
        channel="telegram",
        message="reminder test",
        status=NotificationLogStatus.FAILED.value,
        sent_at=now_in("UTC") - timedelta(minutes=10),
        retry_count=retry_count,
        next_retry_at=next_retry_at,
    )
    db_session.add(log)
    await db_session.commit()
    return log


async def _ok_send(bot: object, event: ReminderEvent) -> str:
    return "12345"


async def _fail_send(bot: object, event: ReminderEvent) -> None:
    return None


def _interval_tolerance(retry_count: int, expected_seconds: int) -> None:
    before = now_in("UTC")
    nxt = _compute_next_retry(retry_count)
    assert nxt is not None
    delta = abs((nxt - before).total_seconds() - expected_seconds)
    assert delta < 2


async def test_compute_next_retry_0() -> None:
    _interval_tolerance(0, 60)


async def test_compute_next_retry_1() -> None:
    _interval_tolerance(1, 300)


async def test_compute_next_retry_2() -> None:
    _interval_tolerance(2, 900)


async def test_compute_next_retry_3() -> None:
    _interval_tolerance(3, 3600)


async def test_compute_next_retry_after_max() -> None:
    nxt = _compute_next_retry(4)
    assert nxt is None


async def test_retry_success_marks_sent(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    event = await _event(db_session, user_id)
    log = await _failed_log(db_session, user_id, event.id)

    processed = await notification_service.retry_failed_notifications(db_session, _BOT, _ok_send)

    assert processed == 1
    assert log.status == NotificationLogStatus.SENT.value
    assert log.next_retry_at is None
    assert log.retry_count == 0


async def test_retry_failure_increments_and_schedules(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    event = await _event(db_session, user_id)
    log = await _failed_log(db_session, user_id, event.id)

    processed = await notification_service.retry_failed_notifications(db_session, _BOT, _fail_send)

    assert processed == 1
    assert log.status == NotificationLogStatus.FAILED.value
    assert log.retry_count == 1
    assert log.next_retry_at is not None


async def test_retry_abandoned_after_max(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    event = await _event(db_session, user_id)
    log = await _failed_log(db_session, user_id, event.id, retry_count=3)

    processed = await notification_service.retry_failed_notifications(db_session, _BOT, _fail_send)

    assert processed == 1
    assert log.status == NotificationLogStatus.ABANDONED.value
    assert log.retry_count == 4
    assert log.next_retry_at is None


async def test_retry_skips_not_due(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    event = await _event(db_session, user_id)
    await _failed_log(
        db_session,
        user_id,
        event.id,
        next_retry_at=now_in("UTC") + timedelta(hours=1),
    )

    processed = await notification_service.retry_failed_notifications(db_session, _BOT, _ok_send)

    assert processed == 0


async def test_retry_skips_at_max_count(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    event = await _event(db_session, user_id)
    await _failed_log(
        db_session,
        user_id,
        event.id,
        retry_count=4,
        next_retry_at=now_in("UTC") - timedelta(minutes=1),
    )

    processed = await notification_service.retry_failed_notifications(db_session, _BOT, _ok_send)

    assert processed == 0


async def test_retry_batch_limit(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    event = await _event(db_session, user_id)
    for _ in range(15):
        await _failed_log(db_session, user_id, event.id)

    processed = await notification_service.retry_failed_notifications(db_session, _BOT, _ok_send)

    assert processed == 10


async def test_retry_abandons_missing_event(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    log = await _failed_log(db_session, user_id, None)

    processed = await notification_service.retry_failed_notifications(db_session, _BOT, _ok_send)

    assert processed == 1
    assert log.status == NotificationLogStatus.ABANDONED.value
    assert log.next_retry_at is None
