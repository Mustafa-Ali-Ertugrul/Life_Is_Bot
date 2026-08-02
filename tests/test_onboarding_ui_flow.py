from collections.abc import Callable
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.onboarding_questions import ONBOARDING_QUESTIONS, QuestionType
from app.core.timezone import now_in
from app.models import BotKey, User
from app.services import onboarding_service, preference_service, step_service, user_service
from app.tgbot import commands, onboarding_handlers
from app.tgbot.keyboards import CB_ANS_PREFIX
from app.tgbot.messages import ONBOARDING_INTRO, WELCOME
from tests.conftest import TELEGRAM_USER_ID, TELEGRAM_USER_ID_2


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


async def _run_flow(
    context: Any,
    choices: dict[str, str] | None = None,
    multi: dict[str, set[str]] | None = None,
) -> Any:
    choices = choices or {}
    multi = multi or {}
    update = _callback_update()
    state = await onboarding_handlers.onboarding_begin(update, context)
    while state == onboarding_handlers.ANSWER:
        index = int(context.user_data["ob_index"])
        question = ONBOARDING_QUESTIONS[index]
        if question.question_type is QuestionType.MULTI_CHOICE:
            context.user_data["ob_multi"] = set(multi.get(question.key, {question.options[0]}))
            update = _callback_update()
            state = await onboarding_handlers.onboarding_multi_done(update, context)
            continue
        if question.question_type is QuestionType.NUMBER_INPUT:
            update = _message_update(choices.get(question.key, "8000"))
            state = await onboarding_handlers.onboarding_number_input(update, context)
            continue
        update = _callback_update()
        update.callback_query.data = CB_ANS_PREFIX + choices.get(question.key, question.options[0])
        state = await onboarding_handlers.onboarding_answer(update, context)
    return update


async def _enabled_bots(db_session: AsyncSession, user_id: int) -> set[BotKey]:
    preferences = await preference_service.list_preferences(db_session, user_id)
    return {p.bot_key_enum for p in preferences if p.enabled}


@pytest.fixture
async def user_id(db_session: AsyncSession) -> int:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    return user.id


@pytest.fixture
def session_factory_patch(patch_uow: Callable[[object], None]) -> None:
    patch_uow(onboarding_handlers)


async def test_flow_mixed_profile_enables_bots(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    update = await _run_flow(
        _context(user_id),
        choices={"b1_chronic": "Evet", "c1_sport_freq": "Haftada 3+", "c4_wants_steps": "Hayır"},
        multi={"e1_goals": {"Rutin takibi", "Spor"}},
    )

    user = await db_session.get(User, user_id)
    assert user is not None
    assert user.profile_type == "mixed"
    assert await _enabled_bots(db_session, user_id) == {
        BotKey.MEDICATION,
        BotKey.SPORT,
        BotKey.SUPPLEMENT,
        BotKey.STEP,
        BotKey.HABIT,
    }
    text = update.effective_message.reply_text.call_args.args[0]
    assert "Spor + Sağlık Takibi" in text


async def test_flow_chronic_profile_enables_bots(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    update = await _run_flow(
        _context(user_id),
        choices={
            "b1_chronic": "Evet",
            "c1_sport_freq": "Hayır",
            "c4_wants_steps": "Hayır",
            "d1_supplements": "Hayır",
        },
    )

    user = await db_session.get(User, user_id)
    assert user is not None
    assert user.profile_type == "chronic"
    assert await _enabled_bots(db_session, user_id) == {BotKey.MEDICATION, BotKey.HABIT}
    text = update.effective_message.reply_text.call_args.args[0]
    assert "Kronik Sağlık Takibi" in text


async def test_flow_general_profile_enables_bots(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    update = await _run_flow(
        _context(user_id),
        choices={
            "b1_chronic": "Hayır",
            "b2_medication": "Hayır",
            "c1_sport_freq": "Hayır",
            "c4_wants_steps": "Hayır",
            "d1_supplements": "Hayır",
        },
    )

    user = await db_session.get(User, user_id)
    assert user is not None
    assert user.profile_type == "general"
    assert await _enabled_bots(db_session, user_id) == {BotKey.HABIT, BotKey.STEP}
    text = update.effective_message.reply_text.call_args.args[0]
    assert "Genel Profil" in text
    assert "Adım botu aktif" in text


async def test_flow_step_goal_updates_daily_target(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    update = await _run_flow(
        _context(user_id),
        choices={
            "b1_chronic": "Hayır",
            "b2_medication": "Hayır",
            "c1_sport_freq": "Hayır",
            "c4_wants_steps": "Evet",
            "c4a_step_goal": "10000",
            "d1_supplements": "Hayır",
        },
    )

    settings = await step_service.get_settings(db_session, user_id)
    assert settings is not None
    assert settings.daily_target == 10000
    assert BotKey.STEP in await _enabled_bots(db_session, user_id)
    text = update.effective_message.reply_text.call_args.args[0]
    assert "Günlük adım hedefi: 10.000" in text


async def test_flow_skip_keeps_profile_none(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    update = _callback_update()
    state = await onboarding_handlers.onboarding_skip(update, _context(user_id))

    assert state == -1
    user = await db_session.get(User, user_id)
    assert user is not None
    assert user.onboarding_skipped is True
    assert user.profile_type is None
    assert user.onboarding_completed_at is None
    answers = await onboarding_service.get_answers(db_session, user_id)
    assert answers == {}


async def test_start_gate_offers_onboarding_then_welcome(
    db_session: AsyncSession, session_factory_patch: None, patch_uow: Callable[[object], None]
) -> None:
    patch_uow(commands)

    user1 = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    await user_service.grant_consent(db_session, user1.id)

    intro_update = _start_update(123456789)
    await commands.cmd_start(intro_update, _context(user1.id))
    intro_text = intro_update.effective_message.reply_text.call_args.args[0]
    assert intro_text == ONBOARDING_INTRO

    user2 = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID_2)
    await user_service.grant_consent(db_session, user2.id)
    user2.onboarding_completed_at = now_in("UTC")
    await db_session.flush()

    welcome_update = _start_update(987654321)
    await commands.cmd_start(welcome_update, _context(user2.id))
    welcome_text = welcome_update.effective_message.reply_text.call_args.args[0]
    assert welcome_text == WELCOME


def _start_update(telegram_id: int) -> Any:
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=telegram_id, username=None, first_name=None),
        effective_message=FakeMessage(),
        callback_query=None,
    )
