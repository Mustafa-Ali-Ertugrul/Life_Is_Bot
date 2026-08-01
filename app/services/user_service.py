from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.timezone import now_in
from app.models import TelegramAccount, User


async def find_user_by_telegram_id(session: AsyncSession, telegram_user_id: str) -> User | None:
    result = await session.execute(
        select(User)
        .join(TelegramAccount)
        .where(TelegramAccount.telegram_user_id == telegram_user_id)
        .options(selectinload(User.telegram_account))
    )
    return result.scalar_one_or_none()


async def find_or_create_by_telegram_id(
    session: AsyncSession,
    telegram_user_id: str,
    username: str | None = None,
    first_name: str | None = None,
) -> User:
    user = await find_user_by_telegram_id(session, telegram_user_id)
    if user is not None:
        if username or first_name:
            account = user.telegram_account
            if account is not None:
                changed = False
                if username and account.username != username:
                    account.username = username
                    changed = True
                if first_name and account.first_name != first_name:
                    account.first_name = first_name
                    changed = True
                if changed:
                    await session.commit()
        return user

    now: datetime = now_in()
    user = User(name=first_name, consent_given=False, is_active=True)
    session.add(user)
    await session.flush()

    account = TelegramAccount(
        user_id=user.id,
        telegram_user_id=telegram_user_id,
        username=username,
        first_name=first_name,
        linked_at=now,
    )
    session.add(account)
    await session.commit()
    result = await session.execute(
        select(User).where(User.id == user.id).options(selectinload(User.telegram_account))
    )
    refreshed = result.scalar_one()
    return refreshed


async def count_active_users(session: AsyncSession) -> int:
    result = await session.execute(select(User).where(User.is_active.is_(True)))
    return len(result.scalars().all())
