from sqlalchemy.ext.asyncio import AsyncSession

from app.services import user_service
from tests.conftest import TELEGRAM_USER_ID


async def test_find_or_create_creates_new_user(db_session: AsyncSession) -> None:
    user = await user_service.find_or_create_by_telegram_id(
        db_session, TELEGRAM_USER_ID, username="ali", first_name="Ali"
    )

    assert user.id is not None
    assert user.name == "Ali"
    assert user.consent_given is False
    assert user.is_active is True
    assert user.telegram_account is not None
    assert user.telegram_account.telegram_user_id == TELEGRAM_USER_ID
    assert user.telegram_account.username == "ali"


async def test_find_or_create_returns_existing_user(db_session: AsyncSession) -> None:
    first = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    second = await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)

    assert first.id == second.id


async def test_find_or_create_updates_username(db_session: AsyncSession) -> None:
    await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID, username="eski")
    user = await user_service.find_or_create_by_telegram_id(
        db_session, TELEGRAM_USER_ID, username="yeni"
    )

    assert user.telegram_account is not None
    assert user.telegram_account.username == "yeni"


async def test_count_active_users(db_session: AsyncSession) -> None:
    await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    count = await user_service.count_active_users(db_session)

    assert count == 1


async def test_count_active_users_excludes_inactive(db_session: AsyncSession) -> None:
    await user_service.find_or_create_by_telegram_id(db_session, TELEGRAM_USER_ID)
    user = await user_service.find_user_by_telegram_id(db_session, TELEGRAM_USER_ID)
    assert user is not None
    user.is_active = False
    await db_session.commit()

    count = await user_service.count_active_users(db_session)

    assert count == 0
