from datetime import datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BotKey, ReminderEvent, ReminderStatus, ResponseType, UserResponse
from app.services import reminder_service, response_service, user_service
from app.tgbot import callbacks
from app.tgbot.callback_parser import ReminderAction, ReminderCallback, parse
from tests.conftest import TELEGRAM_USER_ID


class FakeCallbackQuery:
    def __init__(self) -> None:
        self.edit_message_text = AsyncMock()
        self.answer = AsyncMock()


def _fake_query() -> Any:
    return FakeCallbackQuery()


def _context(user_id: int) -> Any:
    return SimpleNamespace(user_data={"user_id": user_id})


def _update() -> Any:
    return SimpleNamespace(effective_message=None, effective_user=None, callback_query=None)


@pytest.fixture
async def user_id(db_session: AsyncSession) -> int:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    return user.id


@pytest.fixture
def session_factory_patch(monkeypatch: pytest.MonkeyPatch, db_session: AsyncSession) -> None:
    monkeypatch.setattr(callbacks, "async_session_factory", lambda: db_session)


async def _medication_event(db_session: AsyncSession, user_id: int) -> ReminderEvent:
    return await reminder_service.create_event(
        db_session,
        user_id=user_id,
        bot_key=BotKey.MEDICATION,
        scheduled_at=datetime(2026, 8, 1, 8, 0),
    )


async def test_response_taken_stores_value(user_id: int, db_session: AsyncSession) -> None:
    event = await _medication_event(db_session, user_id)

    response = await response_service.save_response(
        db_session,
        reminder_event_id=event.id,
        user_id=user_id,
        bot_key=BotKey.MEDICATION,
        response=ResponseType.TAKEN,
    )

    assert response.response == "taken"
    assert response.bot_key == "medication_bot"
    assert response.is_current is True

    result = await db_session.execute(select(ReminderEvent).where(ReminderEvent.id == event.id))
    updated = result.scalar_one()
    assert updated.status == ReminderStatus.POSITIVE.value


async def test_response_not_taken_stores_value(user_id: int, db_session: AsyncSession) -> None:
    event = await _medication_event(db_session, user_id)

    response = await response_service.save_response(
        db_session,
        reminder_event_id=event.id,
        user_id=user_id,
        bot_key=BotKey.MEDICATION,
        response=ResponseType.NOT_TAKEN,
    )

    assert response.response == "not_taken"
    assert response.is_current is True

    result = await db_session.execute(select(ReminderEvent).where(ReminderEvent.id == event.id))
    updated = result.scalar_one()
    assert updated.status == ReminderStatus.NEGATIVE.value


async def test_response_change_keeps_single_current(user_id: int, db_session: AsyncSession) -> None:
    event = await _medication_event(db_session, user_id)
    await response_service.save_response(
        db_session,
        reminder_event_id=event.id,
        user_id=user_id,
        bot_key=BotKey.MEDICATION,
        response=ResponseType.TAKEN,
    )
    await response_service.save_response(
        db_session,
        reminder_event_id=event.id,
        user_id=user_id,
        bot_key=BotKey.MEDICATION,
        response=ResponseType.NOT_TAKEN,
    )

    result = await db_session.execute(
        select(UserResponse).where(UserResponse.reminder_event_id == event.id)
    )
    responses = result.scalars().all()
    assert len(responses) == 2
    assert sum(r.is_current for r in responses) == 1
    assert next(r for r in responses if r.is_current).response == "not_taken"


async def test_reminder_callback_taken(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    event = await _medication_event(db_session, user_id)
    parsed = parse(f"r:{event.id}:t")
    assert isinstance(parsed, ReminderCallback)

    query = _fake_query()
    await callbacks._handle_reminder_callback(_update(), _context(user_id), query, parsed)

    query.edit_message_text.assert_awaited_once_with("Aldım ✅")
    result = await db_session.execute(
        select(UserResponse).where(
            UserResponse.reminder_event_id == event.id,
            UserResponse.is_current.is_(True),
        )
    )
    stored = result.scalar_one()
    assert stored.response == "taken"


async def test_reminder_callback_not_taken(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    event = await _medication_event(db_session, user_id)
    parsed = parse(f"r:{event.id}:f")
    assert isinstance(parsed, ReminderCallback)

    query = _fake_query()
    await callbacks._handle_reminder_callback(_update(), _context(user_id), query, parsed)

    query.edit_message_text.assert_awaited_once_with("Almadım ❌")
    result = await db_session.execute(
        select(UserResponse).where(
            UserResponse.reminder_event_id == event.id,
            UserResponse.is_current.is_(True),
        )
    )
    stored = result.scalar_one()
    assert stored.response == "not_taken"


async def test_reminder_callback_missing_event(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    parsed = ReminderCallback(event_id=999_999, action=ReminderAction.TAKEN)

    query = _fake_query()
    await callbacks._handle_reminder_callback(_update(), _context(user_id), query, parsed)

    query.answer.assert_awaited_once_with("Bildirim bulunamadı", show_alert=True)
