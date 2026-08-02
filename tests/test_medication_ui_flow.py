from datetime import timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from telegram.ext import ConversationHandler

from app.core.timezone import now_in
from app.services import medication_service, settings_service, user_service
from app.tgbot import medication_handlers
from app.tgbot.callback_parser import MedicationAction, UICallback, UICallbackKind
from app.tgbot.messages import MED_CANCELLED, MED_CREATED
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
def session_factory_patch(monkeypatch: pytest.MonkeyPatch, db_session: AsyncSession) -> None:
    monkeypatch.setattr(medication_handlers, "async_session_factory", lambda: db_session)


async def test_flow_full_conversation_creates_plan(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    context = _context(user_id)

    state = await medication_handlers.medication_add_command(_message_update(), context)
    assert state == medication_handlers.ASK_NAME

    state = await medication_handlers.medication_ask_name(_message_update("Metformin"), context)
    assert state == medication_handlers.ASK_DOSE

    state = await medication_handlers.medication_ask_dose(_message_update("500mg"), context)
    assert state == medication_handlers.ASK_WITH_FOOD

    state = await medication_handlers.medication_ask_with_food(
        _message_update("Aç karnına"), context
    )
    assert state == medication_handlers.ASK_DAYS

    state = await medication_handlers.medication_ask_days(_message_update("pzt, çar, cum"), context)
    assert state == medication_handlers.ASK_TIME

    state = await medication_handlers.medication_ask_time(_message_update("08:00"), context)
    assert state == medication_handlers.ASK_DURATION

    state = await medication_handlers.medication_ask_duration(_message_update("0"), context)
    assert state == medication_handlers.ASK_NOTES

    state = await medication_handlers.medication_ask_notes(
        _message_update("Sabah aç karnına"), context
    )
    assert state == medication_handlers.CONFIRM
    assert context.user_data["med_draft_name"] == "Metformin"

    callback_update = _callback_update()
    state = await medication_handlers.medication_confirm_callback(callback_update, context)
    assert state == ConversationHandler.END
    assert callback_update.callback_query.edit_message_text.call_args.args[0] == MED_CREATED

    plans = await medication_service.list_medication_plans(db_session, user_id)
    assert len(plans) == 1
    plan = plans[0]
    assert plan.name == "Metformin"
    assert plan.dose == "500mg"
    assert plan.days_of_week == "1,3,5"
    assert (plan.target_hour, plan.target_minute) == (8, 0)
    assert plan.notes == "Sabah aç karnına"
    assert plan.is_active is True


async def test_flow_skip_optional_fields(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    context = _context(user_id)

    await medication_handlers.medication_add_command(_message_update(), context)
    await medication_handlers.medication_ask_name(_message_update("Aspirin"), context)
    state = await medication_handlers.medication_ask_dose(_message_update("yok"), context)
    assert state == medication_handlers.ASK_WITH_FOOD
    state = await medication_handlers.medication_ask_with_food(
        _message_update("Aç karnına"), context
    )
    assert state == medication_handlers.ASK_DAYS
    state = await medication_handlers.medication_ask_days(_message_update(""), context)
    assert state == medication_handlers.ASK_TIME
    await medication_handlers.medication_ask_time(_message_update("21:30"), context)
    state = await medication_handlers.medication_ask_duration(_message_update("0"), context)
    assert state == medication_handlers.ASK_NOTES
    state = await medication_handlers.medication_ask_notes(_message_update("yok"), context)
    assert state == medication_handlers.CONFIRM

    await medication_handlers.medication_confirm_callback(_callback_update(), context)

    plans = await medication_service.list_medication_plans(db_session, user_id)
    assert len(plans) == 1
    assert plans[0].dose is None
    assert plans[0].notes is None
    assert plans[0].days_of_week == "1,2,3,4,5,6,7"


async def test_flow_finite_duration_sets_dates(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    user_settings = await settings_service.get_settings(db_session, user_id)
    today = now_in(user_settings.timezone).date()
    expected_end = today + timedelta(days=13)

    context = _context(user_id)
    await medication_handlers.medication_add_command(_message_update(), context)
    await medication_handlers.medication_ask_name(_message_update("Antibiyotik"), context)
    await medication_handlers.medication_ask_dose(_message_update("1x1"), context)
    await medication_handlers.medication_ask_with_food(_message_update("Aç karnına"), context)
    await medication_handlers.medication_ask_days(_message_update("her gün"), context)
    await medication_handlers.medication_ask_time(_message_update("12:00"), context)
    state = await medication_handlers.medication_ask_duration(_message_update("14"), context)
    assert state == medication_handlers.ASK_NOTES
    await medication_handlers.medication_ask_notes(_message_update("yok"), context)

    await medication_handlers.medication_confirm_callback(_callback_update(), context)

    plans = await medication_service.list_medication_plans(db_session, user_id)
    assert len(plans) == 1
    assert plans[0].start_date == today
    assert plans[0].end_date == expected_end


async def test_flow_list_then_detail_navigation(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    plan = await medication_service.create_medication_plan(
        db_session,
        user_id,
        "Metformin",
        target_hour=8,
        target_minute=0,
        days_of_week="1,3,5",
        dose="500mg",
        with_food="empty",
    )

    list_update = _callback_update()
    await medication_handlers.medication_list_callback(
        list_update, _context(user_id), _med_callback(MedicationAction.LIST)
    )
    list_text = list_update.callback_query.edit_message_text.call_args.args[0]
    assert "Metformin" in list_text
    assert "İlaç planların" in list_text

    detail_update = _callback_update()
    await medication_handlers.medication_detail_callback(
        detail_update,
        _context(user_id),
        _med_callback(MedicationAction.DETAIL, plan.id),
    )
    detail_text = detail_update.callback_query.edit_message_text.call_args.args[0]
    assert "Metformin" in detail_text
    assert "500mg" in detail_text
    assert "08:00" in detail_text


async def test_flow_toggle_plan(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    plan = await medication_service.create_medication_plan(
        db_session,
        user_id,
        "Metformin",
        target_hour=8,
        target_minute=0,
        days_of_week="1,2,3,4,5,6,7",
    )

    toggle_update = _callback_update()
    await medication_handlers.medication_toggle_callback(
        toggle_update,
        _context(user_id),
        _med_callback(MedicationAction.TOGGLE, plan.id),
    )

    toggled = await medication_service.get_medication_plan(db_session, plan.id)
    assert toggled is not None
    assert toggled.is_active is False
    toggle_update.callback_query.answer.assert_awaited_once()


async def test_flow_cancel_mid_conversation(
    user_id: int, db_session: AsyncSession, session_factory_patch: None
) -> None:
    context = _context(user_id)
    await medication_handlers.medication_add_command(_message_update(), context)
    state = await medication_handlers.medication_ask_name(_message_update("Metformin"), context)
    assert state == medication_handlers.ASK_DOSE

    cancel_update = _message_update()
    state = await medication_handlers.cancel(cancel_update, context)
    assert state == ConversationHandler.END
    assert cancel_update.effective_message.reply_text.call_args.args[0] == MED_CANCELLED

    plans = await medication_service.list_medication_plans(db_session, user_id)
    assert len(plans) == 0
