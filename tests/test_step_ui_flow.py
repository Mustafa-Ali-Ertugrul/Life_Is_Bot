from collections.abc import Callable
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram.ext import ConversationHandler

from app.core.timezone import now_in
from app.models import StepLog
from app.services import settings_service, step_service, user_service
from app.tgbot import step_handlers
from app.tgbot.callback_parser import StepAction, UICallback, UICallbackKind
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


async def test_flow_log_steps(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    menu_update = _message_update()
    await step_handlers.step_menu_command(menu_update, _context(user_id))

    callback_update = _callback_update()
    state = await step_handlers.step_log_callback(callback_update, _context(user_id))
    assert state == step_handlers.ASK_STEPS

    steps_update = _message_update("7500")
    state = await step_handlers.step_ask_steps(steps_update, _context(user_id))
    assert state == ConversationHandler.END

    today = await step_service.get_today_steps(db_session, user_id)
    assert today is not None
    assert today.steps == 7500


async def test_flow_update_goal(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    callback_update = _callback_update()
    state = await step_handlers.step_goal_callback(callback_update, _context(user_id))
    assert state == step_handlers.ASK_GOAL

    goal_update = _message_update("12000")
    state = await step_handlers.step_ask_goal(goal_update, _context(user_id))
    assert state == ConversationHandler.END

    settings = await step_service.get_settings(db_session, user_id)
    assert settings is not None
    assert settings.daily_target == 12000


async def test_flow_toggle_off(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    callback_update = _callback_update()
    await step_handlers.step_settings_callback(
        callback_update, _context(user_id), _step_callback(StepAction.SETTINGS)
    )

    toggle_update = _callback_update()
    await step_handlers.step_toggle_callback(
        toggle_update, _context(user_id), _step_callback(StepAction.TOGGLE)
    )

    settings = await step_service.get_settings(db_session, user_id)
    assert settings is not None
    assert settings.is_active is False


async def test_flow_cancel_keeps_state(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    callback_update = _callback_update()
    state = await step_handlers.step_log_callback(callback_update, _context(user_id))
    assert state == step_handlers.ASK_STEPS

    cancel_update = _message_update()
    state = await step_handlers.step_cancel(cancel_update, _context(user_id))
    assert state == ConversationHandler.END

    today = await step_service.get_today_steps(db_session, user_id)
    assert today is None


async def test_flow_upsert_same_day(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    await step_handlers.step_ask_steps(_message_update("5000"), _context(user_id))
    await step_handlers.step_ask_steps(_message_update("9000"), _context(user_id))

    result = await db_session.execute(select(StepLog).where(StepLog.user_id == user_id))
    logs = result.scalars().all()
    assert len(logs) == 1
    assert logs[0].steps == 9000


async def test_flow_days_update(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    callback_update = _callback_update()
    state = await step_handlers.step_days_callback(callback_update, _context(user_id))
    assert state == step_handlers.ASK_DAYS

    days_update = _message_update("pzt, sal, çar, per, cum")
    state = await step_handlers.step_ask_days(days_update, _context(user_id))
    assert state == ConversationHandler.END

    settings = await step_service.get_settings(db_session, user_id)
    assert settings is not None
    assert settings.days_of_week == "1,2,3,4,5"


async def test_flow_menu_after_log_reflects_progress(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    user_settings = await settings_service.get_settings(db_session, user_id)
    local_date = now_in(user_settings.timezone).date()
    await step_service.log_steps(db_session, user_id, 7500, local_date)

    menu_update = _message_update()
    await step_handlers.step_menu_command(menu_update, _context(user_id))

    text = menu_update.effective_message.reply_text.call_args.args[0]
    assert "7.500" in text
