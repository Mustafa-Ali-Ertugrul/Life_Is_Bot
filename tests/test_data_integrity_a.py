from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone import now_in
from app.models import (
    BotKey,
    ReminderEvent,
    ReminderStatus,
    ResponseType,
    TelegramAccount,
    UserResponse,
)
from app.services import reminder_service, response_service, user_service
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


def test_build_reminder_dedupe_key_format() -> None:
    key = reminder_service.build_reminder_dedupe_key("habit_bot", "habit", 7, date(2026, 8, 1))
    assert key == "habit_bot:habit:7:2026-08-01"


def test_build_reminder_dedupe_key_none_related() -> None:
    key = reminder_service.build_reminder_dedupe_key("step_bot", None, None, date(2026, 8, 1))
    assert key == "step_bot:none:0:2026-08-01"


async def test_create_event_sets_dedupe_fields(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    event = await reminder_service.create_event(
        db_session,
        user_id=user_id,
        bot_key=BotKey.HABIT,
        scheduled_at=datetime(2026, 8, 1, 8, 0, tzinfo=UTC),
        related_type="habit",
        related_id=3,
    )

    assert event.scheduled_local_date == date(2026, 8, 1)
    assert event.dedupe_key == "habit_bot:habit:3:2026-08-01"


async def test_create_event_idempotent_without_related(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    when = now_in("UTC").replace(hour=9, minute=0, second=0, microsecond=0)

    first = await reminder_service.create_event(
        db_session, user_id=user_id, bot_key=BotKey.STEP, scheduled_at=when
    )
    second = await reminder_service.create_event(
        db_session, user_id=user_id, bot_key=BotKey.STEP, scheduled_at=when + timedelta(hours=1)
    )

    assert second.id == first.id


async def test_create_event_allows_duplicate_different_bot_same_day(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session)
    when = now_in("UTC").replace(hour=9, minute=0, second=0, microsecond=0)

    first = await reminder_service.create_event(
        db_session, user_id=user_id, bot_key=BotKey.STEP, scheduled_at=when
    )
    second = await reminder_service.create_event(
        db_session, user_id=user_id, bot_key=BotKey.SUPPLEMENT, scheduled_at=when
    )

    assert second.id != first.id


async def test_create_event_reactivates_cancelled_same_day(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    when = now_in("UTC").replace(hour=9, minute=0, second=0, microsecond=0)

    event = await _event(db_session, user_id, when=when)
    event.status = ReminderStatus.CANCELLED.value
    await db_session.commit()

    reactivated = await _event(db_session, user_id, when=when + timedelta(minutes=30))

    assert reactivated.id == event.id
    assert reactivated.status == ReminderStatus.SCHEDULED.value
    assert reactivated.notified_at is None
    scheduled = reactivated.scheduled_at.replace(tzinfo=when.tzinfo)
    assert scheduled >= when + timedelta(minutes=29)


async def test_telegram_account_unique_per_user(db_session: AsyncSession) -> None:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)

    db_session.add(
        TelegramAccount(
            user_id=user.id,
            telegram_user_id="999888777",
            username=None,
            first_name=None,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_user_response_single_current_per_event(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    event = await _event(db_session, user_id)

    db_session.add(
        UserResponse(
            reminder_event_id=event.id,
            user_id=user_id,
            bot_key=BotKey.HABIT.value,
            response="done",
            source="test",
            responded_at=now_in(),
            is_current=True,
        )
    )
    await db_session.flush()

    db_session.add(
        UserResponse(
            reminder_event_id=event.id,
            user_id=user_id,
            bot_key=BotKey.HABIT.value,
            response="not_done",
            source="test",
            responded_at=now_in(),
            is_current=True,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_save_response_keeps_single_current(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    event = await _event(db_session, user_id)

    await response_service.save_response(
        db_session, event.id, user_id, BotKey.HABIT, ResponseType.DONE
    )
    await response_service.save_response(
        db_session, event.id, user_id, BotKey.HABIT, ResponseType.NOT_DONE
    )

    result = await db_session.execute(
        select(UserResponse).where(UserResponse.reminder_event_id == event.id)
    )
    responses = list(result.scalars().all())

    assert len(responses) == 2
    assert sum(1 for r in responses if r.is_current) == 1
