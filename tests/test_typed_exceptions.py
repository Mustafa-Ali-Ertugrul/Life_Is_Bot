from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import errors
from app.core.errors import (
    AppError,
    InvalidStateError,
    NotFoundError,
    PermissionDeniedError,
)
from app.models import BotKey
from app.services import (
    medication_service,
    preference_service,
    settings_service,
    step_service,
    supplement_service,
    user_service,
)
from tests.conftest import TELEGRAM_USER_ID


async def _user_id(db_session: AsyncSession) -> int:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    return user.id


async def test_medication_create_empty_name_raises_invalid_state(db_session: AsyncSession) -> None:
    user_id = await _user_id(db_session)

    with pytest.raises(InvalidStateError, match="name must not be empty"):
        await medication_service.create_medication_plan(db_session, user_id, "  ", 8, 0, "1,3,5")


async def test_medication_update_missing_raises_not_found(db_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError, match="MedicationPlan 99999 not found"):
        await medication_service.update_medication_plan(db_session, 99999, name="X")


async def test_step_update_daily_target_raises_invalid_state(db_session: AsyncSession) -> None:
    user_id = await _user_id(db_session)

    with pytest.raises(InvalidStateError, match="daily_target must be between 0 and 100000"):
        await step_service.update_daily_target(db_session, user_id, -1)


async def test_settings_update_timezone_raises_invalid_state(db_session: AsyncSession) -> None:
    user_id = await _user_id(db_session)

    with pytest.raises(InvalidStateError, match="Geçersiz timezone"):
        await settings_service.update_timezone(db_session, user_id, "Mars/Olympus")


async def test_settings_get_missing_raises_not_found(db_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError, match="Kullanıcı bulunamadı"):
        await settings_service.get_settings(db_session, 999_999)


async def test_supplement_invalid_with_food_raises_invalid_state(db_session: AsyncSession) -> None:
    user_id = await _user_id(db_session)

    with pytest.raises(InvalidStateError, match="with_food must be one of"):
        await supplement_service.create_supplement_plan(
            db_session, user_id, "Demir", "1,2,3,4,5", 12, 0, with_food="breakfast"
        )


async def test_supplement_inverted_date_range_raises_invalid_state(
    db_session: AsyncSession,
) -> None:
    user_id = await _user_id(db_session)

    with pytest.raises(InvalidStateError, match="start_date must not be after end_date"):
        await supplement_service.create_supplement_plan(
            db_session,
            user_id,
            "Demir",
            "1,2,3,4,5",
            12,
            0,
            start_date=date(2026, 8, 10),
            end_date=date(2026, 8, 1),
        )


async def test_preference_core_toggle_raises_permission_denied(db_session: AsyncSession) -> None:
    user_id = await _user_id(db_session)

    with pytest.raises(PermissionDeniedError, match="Ana bot kapatılamaz"):
        await preference_service.toggle_preference(db_session, user_id, BotKey.CORE, enabled=True)


async def test_user_grant_consent_missing_raises_not_found(db_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError, match="Kullanıcı bulunamadı"):
        await user_service.grant_consent(db_session, 999_999)


def test_typed_exceptions_are_app_error_subclasses() -> None:
    assert issubclass(InvalidStateError, AppError)
    assert issubclass(NotFoundError, AppError)
    assert issubclass(PermissionDeniedError, AppError)
    assert issubclass(AppError, Exception)


def test_errors_module_exports_full_hierarchy() -> None:
    assert errors.__all__ == [
        "AppError",
        "InvalidStateError",
        "NotFoundError",
        "PermissionDeniedError",
    ]


def test_exception_messages_preserved() -> None:
    assert str(InvalidStateError("name must not be empty")) == "name must not be empty"
    assert str(NotFoundError("Kullanıcı bulunamadı: 999999")) == "Kullanıcı bulunamadı: 999999"
    assert str(PermissionDeniedError("Ana bot kapatılamaz.")) == "Ana bot kapatılamaz."
