from collections.abc import Callable
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from telegram.ext import ConversationHandler

from app.core.onboarding_questions import ONBOARDING_QUESTIONS, QuestionType
from app.models import User
from app.services import onboarding_service, user_service
from app.tgbot import onboarding_handlers
from app.tgbot.keyboards import CB_ANS_PREFIX, CB_TOGGLE_PREFIX, onboarding_question_keyboard
from app.tgbot.messages import (
    ONBOARDING_CANCELLED,
    ONBOARDING_CHOICE_HINT,
    ONBOARDING_INVALID_NUMBER,
    ONBOARDING_MULTI_HINT,
)
from tests.conftest import TELEGRAM_USER_ID


class FakeMessage:
    def __init__(self, text: str | None = None) -> None:
        self.text = text
        self.reply_text = AsyncMock()


class FakeCallbackQuery:
    def __init__(self) -> None:
        self.data: str | None = None
        self.edit_message_text = AsyncMock()
        self.answer = AsyncMock()


def _message_update(text: str | None = None) -> Any:
    return SimpleNamespace(
        effective_message=FakeMessage(text),
        effective_user=None,
        callback_query=None,
    )


def _callback_update(text: str | None = None) -> Any:
    return SimpleNamespace(
        effective_message=FakeMessage(text),
        effective_user=None,
        callback_query=FakeCallbackQuery(),
    )


def _context(user_id: int) -> Any:
    return SimpleNamespace(user_data={"user_id": user_id})


def _question_index(key: str) -> int:
    return next(i for i, q in enumerate(ONBOARDING_QUESTIONS) if q.key == key)


def _setup_at(context: Any, key: str) -> None:
    context.user_data["ob_index"] = _question_index(key)
    context.user_data["ob_answers"] = {}
    context.user_data["ob_multi"] = set()


@pytest.fixture
async def user_id(db_session: AsyncSession) -> int:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    return user.id


@pytest.fixture
def session_factory_patch(patch_uow: Callable[[object], None]) -> None:
    patch_uow(onboarding_handlers)


async def test_begin_shows_first_question(user_id: int, session_factory_patch: None) -> None:
    update = _callback_update()
    state = await onboarding_handlers.onboarding_begin(update, _context(user_id))

    assert state == onboarding_handlers.ANSWER
    text = update.callback_query.edit_message_text.call_args.args[0]
    assert "(1/20)" in text
    assert "Cinsiyetiniz?" in text
    keyboard = update.callback_query.edit_message_text.call_args.kwargs["reply_markup"]
    rows = keyboard.inline_keyboard
    assert [button.text for row in rows for button in row] == [
        "Kadın",
        "Erkek",
        "Diğer",
        "Belirtmek istemiyorum",
    ]


async def test_skip_marks_user_skipped(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    update = _callback_update()
    state = await onboarding_handlers.onboarding_skip(update, _context(user_id))

    assert state == ConversationHandler.END
    user = await db_session.get(User, user_id)
    assert user is not None
    assert user.onboarding_skipped is True
    assert user.profile_type is None


async def test_answer_advances_to_next_question(user_id: int, session_factory_patch: None) -> None:
    context = _context(user_id)
    begin_update = _callback_update()
    await onboarding_handlers.onboarding_begin(begin_update, context)

    update = _callback_update()
    update.callback_query.data = CB_ANS_PREFIX + "Erkek"
    state = await onboarding_handlers.onboarding_answer(update, context)

    assert state == onboarding_handlers.ANSWER
    assert context.user_data["ob_answers"]["a1_gender"] == "Erkek"
    text = update.callback_query.edit_message_text.call_args.args[0]
    assert "(2/20)" in text
    assert "Yaş aralığınız?" in text


async def test_answer_yes_no_branch_advances(user_id: int, session_factory_patch: None) -> None:
    context = _context(user_id)
    _setup_at(context, "b1_chronic")

    update = _callback_update()
    update.callback_query.data = CB_ANS_PREFIX + "Evet"
    state = await onboarding_handlers.onboarding_answer(update, context)

    assert state == onboarding_handlers.ANSWER
    assert context.user_data["ob_answers"]["b1_chronic"] == "Evet"
    text = update.callback_query.edit_message_text.call_args.args[0]
    assert "Düzenli ilaç" in text


async def test_number_input_invalid_stays(user_id: int, session_factory_patch: None) -> None:
    context = _context(user_id)
    _setup_at(context, "c4a_step_goal")

    low_update = _message_update("500")
    state = await onboarding_handlers.onboarding_number_input(low_update, context)
    assert state == onboarding_handlers.ANSWER
    assert low_update.effective_message.reply_text.call_args.args[0] == ONBOARDING_INVALID_NUMBER

    text_update = _message_update("abc")
    state = await onboarding_handlers.onboarding_number_input(text_update, context)
    assert state == onboarding_handlers.ANSWER
    assert text_update.effective_message.reply_text.call_args.args[0] == ONBOARDING_INVALID_NUMBER


async def test_number_input_valid_advances(user_id: int, session_factory_patch: None) -> None:
    context = _context(user_id)
    _setup_at(context, "c4a_step_goal")

    update = _message_update("8.000")
    state = await onboarding_handlers.onboarding_number_input(update, context)

    assert state == onboarding_handlers.ANSWER
    assert context.user_data["ob_answers"]["c4a_step_goal"] == "8000"
    text = update.effective_message.reply_text.call_args.args[0]
    assert "Takviye" in text


async def test_number_input_lenient_text_advances(
    user_id: int, session_factory_patch: None
) -> None:
    context = _context(user_id)
    _setup_at(context, "c4a_step_goal")

    update = _message_update("8000 adım")
    state = await onboarding_handlers.onboarding_number_input(update, context)

    assert state == onboarding_handlers.ANSWER
    assert context.user_data["ob_answers"]["c4a_step_goal"] == "8000"
    text = update.effective_message.reply_text.call_args.args[0]
    assert "Takviye" in text


async def test_number_input_quick_button_advances(
    user_id: int, session_factory_patch: None
) -> None:
    context = _context(user_id)
    _setup_at(context, "c4a_step_goal")

    update = _callback_update()
    update.callback_query.data = CB_ANS_PREFIX + "10000"
    state = await onboarding_handlers.onboarding_answer(update, context)

    assert state == onboarding_handlers.ANSWER
    assert context.user_data["ob_answers"]["c4a_step_goal"] == "10000"
    text = update.callback_query.edit_message_text.call_args.args[0]
    assert "Takviye" in text


def test_number_input_keyboard_has_quick_buttons() -> None:
    question = next(q for q in ONBOARDING_QUESTIONS if q.key == "c4a_step_goal")
    keyboard = onboarding_question_keyboard(question)
    assert keyboard is not None
    rows = keyboard.inline_keyboard
    labels = [button.text for row in rows for button in row]
    assert labels == ["5.000", "7.500", "10.000", "15.000"]
    assert all(
        isinstance(button.callback_data, str) and button.callback_data.startswith(CB_ANS_PREFIX)
        for row in rows
        for button in row
    )


async def test_text_when_buttons_expected_hint(user_id: int, session_factory_patch: None) -> None:
    context = _context(user_id)
    _setup_at(context, "a1_gender")

    update = _message_update("merhaba")
    state = await onboarding_handlers.onboarding_number_input(update, context)

    assert state == onboarding_handlers.ANSWER
    assert update.effective_message.reply_text.call_args.args[0] == ONBOARDING_CHOICE_HINT


async def test_multi_toggle_add_remove(user_id: int, session_factory_patch: None) -> None:
    context = _context(user_id)
    _setup_at(context, "e1_goals")

    add_update = _callback_update()
    add_update.callback_query.data = CB_TOGGLE_PREFIX + "Rutin takibi"
    state = await onboarding_handlers.onboarding_toggle(add_update, context)
    assert state == onboarding_handlers.ANSWER
    assert "Rutin takibi" in context.user_data["ob_multi"]
    assert add_update.callback_query.answer.call_args.args[0] == "Seçildi: Rutin takibi"

    remove_update = _callback_update()
    remove_update.callback_query.data = CB_TOGGLE_PREFIX + "Rutin takibi"
    state = await onboarding_handlers.onboarding_toggle(remove_update, context)
    assert state == onboarding_handlers.ANSWER
    assert "Rutin takibi" not in context.user_data["ob_multi"]
    assert remove_update.callback_query.answer.call_args.args[0] == "Kaldırıldı: Rutin takibi"


async def test_multi_done_empty_hint(user_id: int, session_factory_patch: None) -> None:
    context = _context(user_id)
    _setup_at(context, "e1_goals")

    update = _callback_update()
    state = await onboarding_handlers.onboarding_multi_done(update, context)

    assert state == onboarding_handlers.ANSWER
    assert update.callback_query.answer.call_args.args[0] == ONBOARDING_MULTI_HINT
    assert "e1_goals" not in context.user_data["ob_answers"]


async def test_multi_done_joins_and_advances(user_id: int, session_factory_patch: None) -> None:
    context = _context(user_id)
    _setup_at(context, "e1_goals")
    context.user_data["ob_multi"] = {"Spor", "Adım"}

    update = _callback_update()
    state = await onboarding_handlers.onboarding_multi_done(update, context)

    assert state == onboarding_handlers.ANSWER
    assert context.user_data["ob_answers"]["e1_goals"] == "Adım,Spor"
    text = update.callback_query.edit_message_text.call_args.args[0]
    assert "Hatırlatma sıklığı" in text


async def test_full_flow_finalizes_profile(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    context = _context(user_id)
    update = _callback_update()
    state = await onboarding_handlers.onboarding_begin(update, context)

    while state == onboarding_handlers.ANSWER:
        index = int(context.user_data["ob_index"])
        question = ONBOARDING_QUESTIONS[index]
        if question.question_type is QuestionType.MULTI_CHOICE:
            context.user_data["ob_multi"] = {question.options[0]}
            update = _callback_update()
            state = await onboarding_handlers.onboarding_multi_done(update, context)
            continue
        if question.question_type is QuestionType.NUMBER_INPUT:
            update = _message_update("8000")
            state = await onboarding_handlers.onboarding_number_input(update, context)
            continue
        update = _callback_update()
        update.callback_query.data = CB_ANS_PREFIX + question.options[0]
        state = await onboarding_handlers.onboarding_answer(update, context)

    assert state == ConversationHandler.END
    answers = await onboarding_service.get_answers(db_session, user_id)
    assert len(answers) == len(ONBOARDING_QUESTIONS)
    user = await db_session.get(User, user_id)
    assert user is not None
    assert user.profile_type == "mixed"
    assert user.onboarding_completed_at is not None
    assert user.onboarding_skipped is False
    text = update.effective_message.reply_text.call_args.args[0]
    assert "Profilin oluşturuldu" in text


async def test_cancel_ends_conversation(user_id: int, session_factory_patch: None) -> None:
    update = _message_update()
    state = await onboarding_handlers.onboarding_cancel(update, _context(user_id))

    assert state == ConversationHandler.END
    assert update.effective_message.reply_text.call_args.args[0] == ONBOARDING_CANCELLED
