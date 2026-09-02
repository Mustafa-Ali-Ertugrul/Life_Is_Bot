"""FastAPI dependency injection."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import AuthError, decode_access_token
from app.core.config import Settings, settings
from app.core.database import unit_of_work
from app.models import TelegramAccount, User


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


async def resolve_first_user_id(session: AsyncSession) -> int:
    """Resolve the first registered user id (provisioning/local tooling)."""
    result = await session.execute(
        select(TelegramAccount.user_id).order_by(TelegramAccount.user_id).limit(1)
    )
    user_id = result.scalar_one_or_none()
    if user_id is None:
        raise HTTPException(status_code=401, detail="no users found")
    return user_id


async def get_current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> int:
    """Resolve the authenticated user id from a bearer JWT."""
    if not (authorization and authorization.startswith("Bearer ")):
        raise HTTPException(status_code=401, detail="authentication required")
    token = authorization[7:]
    try:
        user_id = decode_access_token(token)
    except AuthError:
        raise HTTPException(status_code=401, detail="authentication required") from None
    result = await session.execute(
        select(User.id).where(User.id == user_id, User.is_active.is_(True))
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=401, detail="user not registered")
    request.state.user_id = user_id
    return user_id
