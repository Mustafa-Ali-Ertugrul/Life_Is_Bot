from collections.abc import Callable
from datetime import date
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from telegram.ext import ConversationHandler

from app.models import MedicationPlan
from app.services import medication_service, user_service
from app.tgbot import medication_handlers
from app.tgbot.callback_parser import MedicationAction, UICallback, UICallbackKind
from app.tgbot.messages import (
    MED_CANCELLED,
    MED_CREATED,
    MED_INVALID_DAYS,
    MED_INVALID_DURATION,
    MED_INVALID_NAME,
    MED_INVALID_TIME,
    MED_INVALID_WITH_FOOD,
    MED_LIST_EMPTY,
    MED_MENU,
    MED_NOT_FOUND,
    MED_TOGGLED_OFF,
    MED_TOGGLED_ON,
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


def _full_context(user_id: int) -> Any:
    return SimpleNamespace(
        user_data={
            "user_id": user_id,
            "med_draft_name": "Metformin",
            "med_draft_dose": "500mg",
            "med_draft_with_food": "empty",
            "med_draft_days": [1, 3, 5],
            "med_draft_hour": 8,
            "med_draft_minute": 0,
            "med_draft_duration_days": 0,
            "med_draft_start_date": None,
            "med_draft_end_date": None,
            "med_draft_notes": "Aç karnına",
        }
    )


def _med_callback(action: MedicationAction, plan_id: int | None = None) -> UICallback:
    return UICallback(
        kind=UICallbackKind.MEDICATION,
        medication_action=action,
        medication_plan_id=plan_id,
    )


@pytest.fixture
async def user_id(db_session: AsyncSession) -> int:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    return user.id


@pytest.fixture
def session_factory_patch(patch_uow: Callable[[object], None]) -> None:
    patch_uow(medication_handlers)


async def _create_plan(db_session: AsyncSession, user_id: int, **kwargs: Any) -> MedicationPlan:
    return await medication_service.create_medication_plan(
        db_session,
        user_id,
        name=kwargs.pop("name", "Metformin"),
        target_hour=kwargs.pop("target_hour", 8),
        target_minute=kwargs.pop("target_minute", 0),
        days_of_week=kwargs.pop("days_of_week", "1,2,3,4,5,6,7"),
        dose=kwargs.pop("dose", "500mg"),
        with_food=kwargs.pop("with_food", "empty"),
        **kwargs,
    )


async def test_medication_menu_command(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    update = _message_update()
    await medication_handlers.medication_menu_command(update, _context(user_id))

    text = update.effective_message.reply_text.call_args.args[0]
    assert text == MED_MENU


async def test_medication_list_command_empty(user_id: int, session_factory_patch: None) -> None:
    update = _message_update()
    await medication_handlers.medication_list_command(update, _context(user_id))

    text = update.effective_message.reply_text.call_args.args[0]
    assert text == MED_LIST_EMPTY


async def test_medication_list_command_with_plans(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    await _create_plan(db_session, user_id)

    update = _message_update()
    await medication_handlers.medication_list_command(update, _context(user_id))

    text = update.effective_message.reply_text.call_args.args[0]
    assert "Metformin" in text
    assert "İlaç planların" in text


async def test_medication_menu_callback(user_id: int, session_factory_patch: None) -> None:
    update = _callback_update()
    await medication_handlers.medication_menu_callback(
        update, _context(user_id), _med_callback(MedicationAction.MENU)
    )

    text = update.callback_query.edit_message_text.call_args.args[0]
    assert text == MED_MENU
    update.callback_query.answer.assert_awaited_once()


async def test_medication_list_callback_empty(user_id: int, session_factory_patch: None) -> None:
    update = _callback_update()
    await medication_handlers.medication_list_callback(
        update, _context(user_id), _med_callback(MedicationAction.LIST)
    )

    text = update.callback_query.edit_message_text.call_args.args[0]
    assert text == MED_LIST_EMPTY


async def test_medication_list_callback_with_plans(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    await _create_plan(db_session, user_id)

    update = _callback_update()
    await medication_handlers.medication_list_callback(
        update, _context(user_id), _med_callback(MedicationAction.LIST)
    )

    text = update.callback_query.edit_message_text.call_args.args[0]
    assert "Metformin" in text


async def test_medication_detail_callback_found(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    plan = await _create_plan(db_session, user_id)

    update = _callback_update()
    await medication_handlers.medication_detail_callback(
        update,
        _context(user_id),
        _med_callback(MedicationAction.DETAIL, plan.id),
    )

    text = update.callback_query.edit_message_text.call_args.args[0]
    assert "Metformin" in text
    assert "500mg" in text
    assert "Aç karnına" in text
    assert "08:00" in text


async def test_medication_detail_callback_not_found(
    user_id: int, session_factory_patch: None
) -> None:
    update = _callback_update()
    await medication_handlers.medication_detail_callback(
        update,
        _context(user_id),
        _med_callback(MedicationAction.DETAIL, 999),
    )

    text = update.callback_query.edit_message_text.call_args.args[0]
    assert text == MED_NOT_FOUND


async def test_medication_toggle_callback_active_to_inactive(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    plan = await _create_plan(db_session, user_id)

    update = _callback_update()
    await medication_handlers.medication_toggle_callback(
        update,
        _context(user_id),
        _med_callback(MedicationAction.TOGGLE, plan.id),
    )

    toggled = await medication_service.get_medication_plan(db_session, plan.id)
    assert toggled is not None
    assert toggled.is_active is False
    toast = update.callback_query.answer.call_args.args[0]
    assert toast == MED_TOGGLED_OFF


async def test_medication_toggle_callback_inactive_to_active(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    plan = await _create_plan(db_session, user_id)
    await medication_service.toggle_medication_plan(db_session, plan.id, False)

    update = _callback_update()
    await medication_handlers.medication_toggle_callback(
        update,
        _context(user_id),
        _med_callback(MedicationAction.TOGGLE, plan.id),
    )

    toggled = await medication_service.get_medication_plan(db_session, plan.id)
    assert toggled is not None
    assert toggled.is_active is True
    toast = update.callback_query.answer.call_args.args[0]
    assert toast == MED_TOGGLED_ON


async def test_medication_toggle_callback_not_found(
    user_id: int, session_factory_patch: None
) -> None:
    update = _callback_update()
    await medication_handlers.medication_toggle_callback(
        update,
        _context(user_id),
        _med_callback(MedicationAction.TOGGLE, 999),
    )

    text = update.callback_query.edit_message_text.call_args.args[0]
    assert text == MED_NOT_FOUND


async def test_medication_add_command(user_id: int, session_factory_patch: None) -> None:
    update = _message_update()
    state = await medication_handlers.medication_add_command(update, _context(user_id))

    assert state == medication_handlers.ASK_NAME
    text = update.effective_message.reply_text.call_args.args[0]
    assert "İlaç adını" in text


async def test_medication_add_callback(user_id: int, session_factory_patch: None) -> None:
    update = _callback_update()
    state = await medication_handlers.medication_add_callback(update, _context(user_id))

    assert state == medication_handlers.ASK_NAME
    update.callback_query.answer.assert_awaited_once()


async def test_medication_ask_name_valid(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    update = _message_update("Metformin")
    state = await medication_handlers.medication_ask_name(update, _context(user_id))

    assert state == medication_handlers.ASK_DOSE
    assert update.effective_message.reply_text.call_args.args[0].startswith("Doz bilgisini")


async def test_medication_ask_name_empty(user_id: int, session_factory_patch: None) -> None:
    update = _message_update("   ")
    state = await medication_handlers.medication_ask_name(update, _context(user_id))

    assert state == medication_handlers.ASK_NAME
    assert update.effective_message.reply_text.call_args.args[0] == MED_INVALID_NAME


async def test_medication_ask_dose_valid(user_id: int, session_factory_patch: None) -> None:
    update = _message_update("500mg")
    state = await medication_handlers.medication_ask_dose(update, _context(user_id))

    assert state == medication_handlers.ASK_WITH_FOOD


async def test_medication_ask_dose_no_dose(user_id: int, session_factory_patch: None) -> None:
    update = _message_update("yok")
    state = await medication_handlers.medication_ask_dose(update, _context(user_id))

    assert state == medication_handlers.ASK_WITH_FOOD


async def test_medication_ask_with_food_valid(user_id: int, session_factory_patch: None) -> None:
    update = _message_update("Aç karnına")
    state = await medication_handlers.medication_ask_with_food(update, _context(user_id))

    assert state == medication_handlers.ASK_DAYS


async def test_medication_ask_with_food_invalid(user_id: int, session_factory_patch: None) -> None:
    update = _message_update("bilinmeyen")
    state = await medication_handlers.medication_ask_with_food(update, _context(user_id))

    assert state == medication_handlers.ASK_WITH_FOOD
    assert update.effective_message.reply_text.call_args.args[0] == MED_INVALID_WITH_FOOD


async def test_medication_ask_days_valid(user_id: int, session_factory_patch: None) -> None:
    update = _message_update("pzt, çar, cum")
    state = await medication_handlers.medication_ask_days(update, _context(user_id))

    assert state == medication_handlers.ASK_TIME


async def test_medication_ask_days_invalid(user_id: int, session_factory_patch: None) -> None:
    update = _message_update("bilinmeyengün")
    state = await medication_handlers.medication_ask_days(update, _context(user_id))

    assert state == medication_handlers.ASK_DAYS
    assert update.effective_message.reply_text.call_args.args[0] == MED_INVALID_DAYS


async def test_medication_ask_time_valid(user_id: int, session_factory_patch: None) -> None:
    update = _message_update("08:00")
    state = await medication_handlers.medication_ask_time(update, _context(user_id))

    assert state == medication_handlers.ASK_DURATION


async def test_medication_ask_time_invalid(user_id: int, session_factory_patch: None) -> None:
    update = _message_update("25:00")
    state = await medication_handlers.medication_ask_time(update, _context(user_id))

    assert state == medication_handlers.ASK_TIME
    assert update.effective_message.reply_text.call_args.args[0] == MED_INVALID_TIME


async def test_medication_ask_duration_indefinite(
    user_id: int, session_factory_patch: None
) -> None:
    update = _message_update("0")
    state = await medication_handlers.medication_ask_duration(update, _context(user_id))

    assert state == medication_handlers.ASK_NOTES


async def test_medication_ask_duration_finite(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    update = _message_update("14")
    state = await medication_handlers.medication_ask_duration(update, _context(user_id))

    assert state == medication_handlers.ASK_NOTES
    start = update.effective_message.reply_text.call_args.args[0]
    assert "Ek not" in start


async def test_medication_ask_duration_invalid(user_id: int, session_factory_patch: None) -> None:
    update = _message_update("abc")
    state = await medication_handlers.medication_ask_duration(update, _context(user_id))

    assert state == medication_handlers.ASK_DURATION
    assert update.effective_message.reply_text.call_args.args[0] == MED_INVALID_DURATION


async def test_medication_ask_notes_valid(user_id: int, session_factory_patch: None) -> None:
    update = _message_update("Aç karnına, bol su ile")
    state = await medication_handlers.medication_ask_notes(update, _context(user_id))

    assert state == medication_handlers.CONFIRM
    text = update.effective_message.reply_text.call_args.args[0]
    assert "İlaç planı eklensin mi?" in text


async def test_medication_ask_notes_no_notes(user_id: int, session_factory_patch: None) -> None:
    update = _message_update("yok")
    state = await medication_handlers.medication_ask_notes(update, _context(user_id))

    assert state == medication_handlers.CONFIRM


async def test_medication_confirm_callback_creates_plan(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    update = _callback_update()
    state = await medication_handlers.medication_confirm_callback(update, _full_context(user_id))

    assert state == ConversationHandler.END
    text = update.callback_query.edit_message_text.call_args.args[0]
    assert text == MED_CREATED

    plans = await medication_service.list_medication_plans(db_session, user_id)
    assert len(plans) == 1
    plan = plans[0]
    assert plan.name == "Metformin"
    assert plan.dose == "500mg"
    assert plan.with_food == "empty"
    assert plan.days_of_week == "1,3,5"
    assert (plan.target_hour, plan.target_minute) == (8, 0)
    assert plan.notes == "Aç karnına"
    assert plan.is_active is True
    assert plan.start_date is None
    assert plan.end_date is None


async def test_medication_confirm_callback_finite_duration(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    context = _full_context(user_id)
    context.user_data["med_draft_duration_days"] = 14
    context.user_data["med_draft_start_date"] = date(2026, 8, 3)
    context.user_data["med_draft_end_date"] = date(2026, 8, 16)

    update = _callback_update()
    state = await medication_handlers.medication_confirm_callback(update, context)

    assert state == ConversationHandler.END
    plans = await medication_service.list_medication_plans(db_session, user_id)
    assert len(plans) == 1
    assert plans[0].start_date == date(2026, 8, 3)
    assert plans[0].end_date == date(2026, 8, 16)


async def test_medication_cancel_callback(user_id: int, session_factory_patch: None) -> None:
    update = _callback_update()
    state = await medication_handlers.medication_cancel_callback(update, _context(user_id))

    assert state == ConversationHandler.END
    assert update.callback_query.edit_message_text.call_args.args[0] == MED_CANCELLED


async def test_medication_cancel(user_id: int, session_factory_patch: None) -> None:
    update = _message_update()
    state = await medication_handlers.cancel(update, _context(user_id))

    assert state == ConversationHandler.END
    assert update.effective_message.reply_text.call_args.args[0] == MED_CANCELLED


@pytest.mark.filterwarnings("ignore:If 'per_message=False'")
def test_medication_conversation_structure() -> None:
    conversation = medication_handlers.medication_conversation()

    assert len(conversation.entry_points) == 2
    assert set(conversation.states.keys()) == {
        medication_handlers.ASK_NAME,
        medication_handlers.ASK_DOSE,
        medication_handlers.ASK_WITH_FOOD,
        medication_handlers.ASK_DAYS,
        medication_handlers.ASK_TIME,
        medication_handlers.ASK_DURATION,
        medication_handlers.ASK_NOTES,
        medication_handlers.CONFIRM,
    }
    assert any(
        "ilac_ekle" in getattr(handler, "commands", set()) for handler in conversation.entry_points
    )


async def test_days_display_helper() -> None:
    assert medication_handlers._days_display([1, 2, 3, 4, 5, 6, 7]) == "Her gün"
    assert medication_handlers._days_display([1, 3, 5]) == "Pzt, Çar, Cum"
    assert medication_handlers._days_display([]) == "-"
