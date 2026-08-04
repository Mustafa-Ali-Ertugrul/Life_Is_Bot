"""FastAPI dependency injection."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import AuthError, verify_api_key, verify_telegram_init_data
from app.core.config import Settings, settings
from app.core.database import unit_of_work
from app.models import TelegramAccount


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session with unit-of-work transaction boundary."""
    async with unit_of_work() as session:
        yield session


def get_settings() -> Settings:
    """Return application settings."""
    return settings


async def pagination_params(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> tuple[int, int]:
    """Resolve shared pagination query parameters."""
    return limit, offset


async def _resolve_api_key_user(
    session: AsyncSession, request: Request
) -> int:
    """Resolve the first registered user for static API key auth (local tooling)."""
    result = await session.execute(
        select(TelegramAccount.user_id).order_by(TelegramAccount.user_id).limit(1)
    )
    user_id = result.scalar_one_or_none()
    if user_id is None:
        raise HTTPException(status_code=401, detail="no users found")
    request.state.user_id = user_id
    return user_id


async def get_current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header()] = None,
) -> int:
    """Resolve the authenticated user id from Telegram initData or API key."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        try:
            tg_user = verify_telegram_init_data(token)
        except AuthError:
            if verify_api_key(token):
                return await _resolve_api_key_user(session, request)
            raise HTTPException(status_code=401, detail="authentication required") from None
        telegram_user_id = tg_user.get("id")
        if telegram_user_id is None:
            raise HTTPException(status_code=401, detail="missing telegram user id")
        result = await session.execute(
            select(TelegramAccount.user_id).where(
                TelegramAccount.telegram_user_id == str(telegram_user_id)
            )
        )
        user_id = result.scalar_one_or_none()
        if user_id is None:
            raise HTTPException(status_code=401, detail="user not registered")
        request.state.user_id = user_id
        return user_id

    if x_api_key and verify_api_key(x_api_key):
        return await _resolve_api_key_user(session, request)

    raise HTTPException(status_code=401, detail="authentication required")
