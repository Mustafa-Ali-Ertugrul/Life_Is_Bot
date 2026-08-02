from datetime import UTC, datetime

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
    TelegramAccount,
)
from app.services import notification_service, user_service
from app.services.notification_service import _format_abandoned
from tests.conftest import TELEGRAM_USER_ID

_BOT = Bot(token="test")

_calls: list[tuple[str, str]] = []


async def _ok_send(bot: object, chat_id: str, text: str) -> str:
    _calls.append((chat_id, text))
    return "12345"


async def _fail_send(bot: object, chat_id: str, text: str) -> None:
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
        dedupe_key=f"abandoned-test-{bot_key.value}",
        status=ReminderStatus.SCHEDULED.value,
        interpretation_json="{}",
        created_at=datetime(2026, 8, 3, 0, 0, tzinfo=UTC),
    )
    db_session.add(event)
    await db_session.commit()
    return event


async def _abandoned_log(
    db_session: AsyncSession,
    user_id: int,
    event_id: int | None,
    *,
    abandoned_notified: bool = False,
) -> NotificationLog:
    log = NotificationLog(
        reminder_event_id=event_id,
        user_id=user_id,
        channel="telegram",
        message="reminder abandoned",
        status=NotificationLogStatus.ABANDONED.value,
        sent_at=now_in("UTC"),
        abandoned_notified=abandoned_notified,
    )
    db_session.add(log)
    await db_session.commit()
    return log


async def test_notify_abandoned_no_logs(db_session: AsyncSession) -> None:
    _reset_calls()
    await _user(db_session)

    notified = await notification_service.notify_abandoned(db_session, _BOT, _ok_send)

    assert notified == 0
    assert _calls == []


async def test_notify_abandoned_single_log(db_session: AsyncSession) -> None:
    _reset_calls()
    user_id = await _user(db_session)
    event = await _event(db_session, user_id, BotKey.HABIT)
    log = await _abandoned_log(db_session, user_id, event.id)

    notified = await notification_service.notify_abandoned(db_session, _BOT, _ok_send)

    assert notified == 1
    assert len(_calls) == 1
    assert "Rutin" in _calls[0][1]
    assert log.abandoned_notified is True


async def test_notify_abandoned_groups_by_user(db_session: AsyncSession) -> None:
    _reset_calls()
    user_id = await _user(db_session)
    event = await _event(db_session, user_id, BotKey.HABIT)
    await _abandoned_log(db_session, user_id, event.id)
    await _abandoned_log(db_session, user_id, event.id)

    notified = await notification_service.notify_abandoned(db_session, _BOT, _ok_send)

    assert notified == 1
    assert len(_calls) == 1


async def test_notify_abandoned_two_users(db_session: AsyncSession) -> None:
    _reset_calls()
    user_id = await _user(db_session)
    other = await user_service.find_or_create_by_telegram_id(db_session, "555000111")
    other_id = other.id
    event = await _event(db_session, user_id, BotKey.HABIT)
    other_event = await _event(db_session, other_id, BotKey.STEP)
    await _abandoned_log(db_session, user_id, event.id)
    await _abandoned_log(db_session, other_id, other_event.id)

    notified = await notification_service.notify_abandoned(db_session, _BOT, _ok_send)

    assert notified == 2
    assert len(_calls) == 2


async def test_notify_abandoned_skips_already_notified(db_session: AsyncSession) -> None:
    _reset_calls()
    user_id = await _user(db_session)
    event = await _event(db_session, user_id, BotKey.HABIT)
    await _abandoned_log(db_session, user_id, event.id, abandoned_notified=True)

    notified = await notification_service.notify_abandoned(db_session, _BOT, _ok_send)

    assert notified == 0
    assert _calls == []


async def test_notify_abandoned_marks_on_failure(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    event = await _event(db_session, user_id, BotKey.HABIT)
    log = await _abandoned_log(db_session, user_id, event.id)

    notified = await notification_service.notify_abandoned(db_session, _BOT, _fail_send)

    assert notified == 0
    assert log.abandoned_notified is True


async def test_notify_abandoned_without_telegram_account(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    event = await _event(db_session, user_id, BotKey.HABIT)
    log = await _abandoned_log(db_session, user_id, event.id)
    await db_session.execute(delete(TelegramAccount))
    await db_session.commit()

    notified = await notification_service.notify_abandoned(db_session, _BOT, _ok_send)

    assert notified == 0
    assert _calls == []
    assert log.abandoned_notified is True


async def test_format_abandoned_single(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    event = await _event(db_session, user_id, BotKey.MEDICATION)
    log = await _abandoned_log(db_session, user_id, event.id)

    text = await _format_abandoned(db_session, [log])

    assert "İlaç" in text
    assert "gönderilemedi" in text


async def test_format_abandoned_multiple(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    habit_event = await _event(db_session, user_id, BotKey.HABIT)
    med_event = await _event(db_session, user_id, BotKey.MEDICATION)
    logs = [
        await _abandoned_log(db_session, user_id, habit_event.id),
        await _abandoned_log(db_session, user_id, med_event.id),
    ]

    text = await _format_abandoned(db_session, logs)

    assert "2 hatırlatma" in text
    assert "Rutin" in text
    assert "İlaç" in text


async def test_notify_abandoned_batch_limit(db_session: AsyncSession) -> None:
    _reset_calls()
    user_id = await _user(db_session)
    event = await _event(db_session, user_id, BotKey.HABIT)
    logs = [await _abandoned_log(db_session, user_id, event.id) for _ in range(15)]

    notified = await notification_service.notify_abandoned(db_session, _BOT, _ok_send)

    assert notified == 1
    marked = sum(1 for log in logs if log.abandoned_notified)
    assert marked == 10
