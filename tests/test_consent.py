import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import BotKey, ConsentRequirement, consent_requirement_for
from app.services import user_service
from tests.conftest import TELEGRAM_USER_ID


async def test_grant_consent_sets_consented_at(db_session: AsyncSession) -> None:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    assert user.consent_given is False

    granted = await user_service.grant_consent(db_session, user.id)

    assert granted.consent_given is True
    assert granted.consented_at is not None


async def test_grant_consent_idempotent(db_session: AsyncSession) -> None:
    user = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    first = await user_service.grant_consent(db_session, user.id)
    first_consented_at = first.consented_at

    second = await user_service.grant_consent(db_session, user.id)

    assert second.consent_given is True
    assert second.consented_at == first_consented_at


async def test_grant_consent_unknown_user_raises(db_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError, match="Kullanıcı bulunamadı"):
        await user_service.grant_consent(db_session, 999_999)


def test_consent_requirements_mapping() -> None:
    assert consent_requirement_for(BotKey.CORE) is ConsentRequirement.NONE
    assert consent_requirement_for(BotKey.HABIT) is ConsentRequirement.RECOMMENDED
    assert consent_requirement_for(BotKey.ASSESSMENT) is ConsentRequirement.REQUIRED
    assert consent_requirement_for(BotKey.MEDICATION) is ConsentRequirement.REQUIRED
