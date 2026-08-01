from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidStateError, NotFoundError, PermissionDeniedError
from app.models import BotKey, ReminderStatus, ResponseType
from app.services import reminder_service, response_service, user_service
from tests.conftest import TELEGRAM_USER_ID, TELEGRAM_USER_ID_2


async def _user(db_session: AsyncSession, telegram_id: str = TELEGRAM_USER_ID) -> int:
    user = await user_service.find_or_create_by_telegram_id(db_session, telegram_id)
    return user.id


async def _event(db_session: AsyncSession, user_id: int) -> int:
    event = await reminder_service.create_event(
        db_session,
        user_id=user_id,
        bot_key=BotKey.HABIT,
        scheduled_at=datetime(2026, 8, 1, 8, 0),
        related_type="habit",
        related_id=1,
    )
    return event.id


async def test_save_response_rejects_missing_event(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)

    with pytest.raises(NotFoundError):
        await response_service.save_response(
            db_session, 99999, user_id, BotKey.HABIT, ResponseType.DONE
        )


async def test_save_response_rejects_foreign_event(db_session: AsyncSession) -> None:
    owner_id = await _user(db_session, TELEGRAM_USER_ID)
    other_id = await _user(db_session, TELEGRAM_USER_ID_2)
    event_id = await _event(db_session, owner_id)

    with pytest.raises(PermissionDeniedError):
        await response_service.save_response(
            db_session, event_id, other_id, BotKey.HABIT, ResponseType.DONE
        )


async def test_save_response_rejects_cancelled_event(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    event_id = await _event(db_session, user_id)
    event = await reminder_service.get_event(db_session, event_id)
    assert event is not None
    event.status = ReminderStatus.CANCELLED.value
    await db_session.commit()

    with pytest.raises(InvalidStateError):
        await response_service.save_response(
            db_session, event_id, user_id, BotKey.HABIT, ResponseType.DONE
        )


async def test_save_response_rejects_suppressed_event(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    event_id = await _event(db_session, user_id)
    event = await reminder_service.get_event(db_session, event_id)
    assert event is not None
    event.status = ReminderStatus.SUPPRESSED.value
    await db_session.commit()

    with pytest.raises(InvalidStateError):
        await response_service.save_response(
            db_session, event_id, user_id, BotKey.HABIT, ResponseType.DONE
        )


async def test_save_response_allows_snoozed_event(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    event_id = await _event(db_session, user_id)
    event = await reminder_service.get_event(db_session, event_id)
    assert event is not None
    event.status = ReminderStatus.SNOOZED.value
    await db_session.commit()

    response = await response_service.save_response(
        db_session, event_id, user_id, BotKey.HABIT, ResponseType.DONE
    )

    assert response.is_current is True


async def test_save_response_allows_response_change(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    event_id = await _event(db_session, user_id)

    await response_service.save_response(
        db_session, event_id, user_id, BotKey.HABIT, ResponseType.DONE
    )
    await response_service.save_response(
        db_session, event_id, user_id, BotKey.HABIT, ResponseType.NOT_DONE
    )

    current = await response_service.get_current_responses(db_session, event_id)
    assert len(current) == 1
    assert current[0].response == ResponseType.NOT_DONE.value
