from collections.abc import Callable
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram.ext import ConversationHandler

from app.core.schedule import parse_days
from app.core.timezone import now_in
from app.models import StepLog
from app.services import settings_service, step_service, user_service
from app.tgbot import step_handlers
from app.tgbot.callback_parser import StepAction, UICallback, UICallbackKind
from app.tgbot.messages import (
    STEP_CANCELLED,
    STEP_FIRST_ACTIVATION,
    STEP_INVALID_GOAL,
    STEP_INVALID_STEPS,
    STEP_INVALID_TIME,
    STEP_TOGGLED_OFF,
    STEP_TOGGLED_ON,
)
from tests.conftest import TELEGRAM_USER_ID


class FakeMessage:
    def __init__(self, text: str | None = None) -> None:
        self.text = text
        self.reply_text = AsyncMock()


class FakeCallbackQuery:
    def __init__(self) -> None:
        self.edit_message_text = AsyncMock()
        self.answer = AsyncMock()


def _message_update(text: str | None = None) -> Any:
    return SimpleNamespace(
        effective_message=FakeMessage(text),
        effective_user=None,
        callback_query=None,
    )


def _callback_update() -> Any:
    return SimpleNamespace(
        effective_message=None,
        effective_user=None,
        callback_query=FakeCallbackQuery(),
    )


def _context(user_id: int) -> Any:
    return SimpleNamespace(user_data={"user_id": user_id})


def _step_callback(action: StepAction) -> UICallback:
    return UICallback(kind=UICallbackKind.STEP, step_action=action)


@pytest.fixture
async def user_id(db_session: AsyncSession) -> int:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    return user.id


@pytest.fixture
def session_factory_patch(patch_uow: Callable[[object], None]) -> None:
    patch_uow(step_handlers)


async def test_step_menu_command_shows_progress(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    user_settings = await settings_service.get_settings(db_session, user_id)
    local_date = now_in(user_settings.timezone).date()
    await step_service.log_steps(db_session, user_id, 7500, local_date)

    update = _message_update()
    await step_handlers.step_menu_command(update, _context(user_id))

    text = update.effective_message.reply_text.call_args.args[0]
    assert "7.500" in text
    assert "8.000" in text
    assert "Bugün" in text


async def test_step_menu_command_empty_today(user_id: int, session_factory_patch: None) -> None:
    update = _message_update()
    await step_handlers.step_menu_command(update, _context(user_id))

    text = update.effective_message.reply_text.call_args.args[0]
    assert "Henüz adım girilmedi" in text


async def test_step_menu_command_first_activation(
    db_session: AsyncSession, session_factory_patch: None
) -> None:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)

    update = _message_update()
    await step_handlers.step_menu_command(update, _context(user.id))

    calls = update.effective_message.reply_text.call_args_list
    assert len(calls) == 2
    assert calls[0].args[0] == STEP_FIRST_ACTIVATION


async def test_step_settings_callback(user_id: int, session_factory_patch: None) -> None:
    update = _callback_update()
    await step_handlers.step_settings_callback(
        update, _context(user_id), _step_callback(StepAction.SETTINGS)
    )

    text = update.callback_query.edit_message_text.call_args.args[0]
    assert "Adım Ayarları" in text
    assert "8.000" in text
    update.callback_query.answer.assert_awaited_once()


async def test_step_toggle_callback_active_to_inactive(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    update = _callback_update()
    await step_handlers.step_toggle_callback(
        update, _context(user_id), _step_callback(StepAction.TOGGLE)
    )

    settings = await step_service.get_settings(db_session, user_id)
    assert settings is not None
    assert settings.is_active is False
    toast = update.callback_query.answer.call_args.args[0]
    assert toast == STEP_TOGGLED_OFF


async def test_step_toggle_callback_inactive_to_active(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    await step_service.toggle_step_bot(db_session, user_id, False)

    update = _callback_update()
    await step_handlers.step_toggle_callback(
        update, _context(user_id), _step_callback(StepAction.TOGGLE)
    )

    settings = await step_service.get_settings(db_session, user_id)
    assert settings is not None
    assert settings.is_active is True
    toast = update.callback_query.answer.call_args.args[0]
    assert toast == STEP_TOGGLED_ON


async def test_step_ask_steps_valid(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    update = _message_update("7500")
    state = await step_handlers.step_ask_steps(update, _context(user_id))

    assert state == ConversationHandler.END
    today = await step_service.get_today_steps(db_session, user_id)
    assert today is not None
    assert today.steps == 7500


async def test_step_ask_steps_thousands_separator(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    update = _message_update("7.500")
    state = await step_handlers.step_ask_steps(update, _context(user_id))

    assert state == ConversationHandler.END
    today = await step_service.get_today_steps(db_session, user_id)
    assert today is not None
    assert today.steps == 7500


async def test_step_ask_steps_invalid(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    update = _message_update("abc")
    state = await step_handlers.step_ask_steps(update, _context(user_id))

    assert state == step_handlers.ASK_STEPS
    assert update.effective_message.reply_text.call_args.args[0] == STEP_INVALID_STEPS
    today = await step_service.get_today_steps(db_session, user_id)
    assert today is None


async def test_step_ask_steps_negative(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    update = _message_update("-5")
    state = await step_handlers.step_ask_steps(update, _context(user_id))

    assert state == step_handlers.ASK_STEPS
    assert update.effective_message.reply_text.call_args.args[0] == STEP_INVALID_STEPS
    today = await step_service.get_today_steps(db_session, user_id)
    assert today is None


async def test_step_ask_goal_valid(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    update = _message_update("10000")
    state = await step_handlers.step_ask_goal(update, _context(user_id))

    assert state == ConversationHandler.END
    settings = await step_service.get_settings(db_session, user_id)
    assert settings is not None
    assert settings.daily_target == 10000


async def test_step_ask_goal_invalid(user_id: int, session_factory_patch: None) -> None:
    update = _message_update("150000")
    state = await step_handlers.step_ask_goal(update, _context(user_id))

    assert state == step_handlers.ASK_GOAL
    assert update.effective_message.reply_text.call_args.args[0] == STEP_INVALID_GOAL


async def test_step_ask_time_valid(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    update = _message_update("22:30")
    state = await step_handlers.step_ask_time(update, _context(user_id))

    assert state == ConversationHandler.END
    settings = await step_service.get_settings(db_session, user_id)
    assert settings is not None
    assert (settings.reminder_hour, settings.reminder_minute) == (22, 30)


async def test_step_ask_time_invalid(user_id: int, session_factory_patch: None) -> None:
    update = _message_update("25:00")
    state = await step_handlers.step_ask_time(update, _context(user_id))

    assert state == step_handlers.ASK_TIME
    assert update.effective_message.reply_text.call_args.args[0] == STEP_INVALID_TIME


async def test_step_ask_days_valid(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    update = _message_update("pzt, çar, cum")
    state = await step_handlers.step_ask_days(update, _context(user_id))

    assert state == ConversationHandler.END
    settings = await step_service.get_settings(db_session, user_id)
    assert settings is not None
    assert settings.days_of_week == "1,3,5"


async def test_step_ask_days_invalid(user_id: int, session_factory_patch: None) -> None:
    update = _message_update("bilinmeyengün")
    state = await step_handlers.step_ask_days(update, _context(user_id))

    assert state == step_handlers.ASK_DAYS
    assert "Geçersiz gün" in update.effective_message.reply_text.call_args.args[0]


async def test_step_cancel(user_id: int, session_factory_patch: None) -> None:
    update = _message_update()
    state = await step_handlers.step_cancel(update, _context(user_id))

    assert state == ConversationHandler.END
    assert update.effective_message.reply_text.call_args.args[0] == STEP_CANCELLED


@pytest.mark.filterwarnings("ignore:If 'per_message=False'")
def test_step_conversation_structure() -> None:
    conversation = step_handlers.step_conversation()

    assert len(conversation.entry_points) == 5
    assert set(conversation.states.keys()) == {
        step_handlers.ASK_STEPS,
        step_handlers.ASK_GOAL,
        step_handlers.ASK_TIME,
        step_handlers.ASK_DAYS,
    }
    assert any(
        "adim_gir" in getattr(handler, "commands", set()) for handler in conversation.entry_points
    )


async def test_days_display_helper() -> None:
    assert step_handlers._days_display("1,2,3,4,5,6,7") == "Her gün"
    assert step_handlers._days_display("1,3,5") == "Pzt, Çar, Cum"
    assert step_handlers._days_display("") == ""


async def test_pct_helper() -> None:
    assert step_handlers._pct(4000, 8000) == 50
    assert step_handlers._pct(8000, 0) == 0
    assert step_handlers._pct(0, 8000) == 0


async def test_days_saved_uses_service(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    update = _message_update("her gün")
    state = await step_handlers.step_ask_days(update, _context(user_id))

    assert state == ConversationHandler.END
    settings = await step_service.get_settings(db_session, user_id)
    assert settings is not None
    assert parse_days(settings.days_of_week) == {1, 2, 3, 4, 5, 6, 7}
    result = await db_session.execute(select(StepLog).where(StepLog.user_id == user_id))
    assert result.scalars().all() == []
