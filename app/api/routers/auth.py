"""Device token provisioning endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import (
    AuthError,
    create_access_token,
    verify_provisioning_key,
    verify_telegram_init_data,
)
from app.api.deps import get_db, resolve_first_user_id
from app.api.schemas.auth import TokenResponse
from app.core.config import settings
from app.models import TelegramAccount
from app.services import user_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


class TelegramInitDataRequest(BaseModel):
    initData: str  # noqa: N815 - Telegram naming


@router.post("/token", response_model=TokenResponse)
async def issue_token(
    session: Annotated[AsyncSession, Depends(get_db)],
    x_provisioning_key: Annotated[str | None, Header()] = None,
    x_telegram_user_id: Annotated[str | None, Header()] = None,
) -> TokenResponse:
    """Exchange the provisioning key for a long-lived device JWT.

    Requires explicit user selection via X-Telegram-User-Id in multi-user
    environments. Falls back to the first user only when exactly one user
    exists (local dev convenience); otherwise returns 400.
    """
    if not x_provisioning_key or not verify_provisioning_key(x_provisioning_key):
        raise HTTPException(status_code=401, detail="invalid provisioning key")
    if x_telegram_user_id:
        result = await session.execute(
            select(TelegramAccount.user_id).where(
                TelegramAccount.telegram_user_id == x_telegram_user_id
            )
        )
        user_id = result.scalar_one_or_none()
        if user_id is None:
            raise HTTPException(status_code=404, detail="telegram user not found")
        access_token = create_access_token(user_id)
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.jwt_expire_days * 86400,
        )
    count = await session.scalar(select(func.count()).select_from(TelegramAccount))
    if count == 1:
        user_id = await resolve_first_user_id(session)
        access_token = create_access_token(user_id)
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.jwt_expire_days * 86400,
        )
    raise HTTPException(
        status_code=400,
        detail="X-Telegram-User-Id header required for provisioning in multi-user environment",
    )


@router.post("/telegram", response_model=TokenResponse)
async def telegram_auth(
    session: Annotated[AsyncSession, Depends(get_db)],
    body: TelegramInitDataRequest | None = None,
    x_telegram_init_data: Annotated[str | None, Header()] = None,
) -> TokenResponse:
    """Exchange validated Telegram WebApp initData for a JWT."""
    raw = ""
    if body and body.initData:
        raw = body.initData
    elif x_telegram_init_data:
        raw = x_telegram_init_data
    if not raw:
        raise HTTPException(status_code=401, detail="initData required")
    try:
        parsed = verify_telegram_init_data(raw)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    user_dict = parsed.get("user_dict")
    if not user_dict or "id" not in user_dict:
        raise HTTPException(status_code=401, detail="user not found in initData")
    telegram_user_id = str(user_dict["id"])
    username = user_dict.get("username")
    first_name = user_dict.get("first_name")
    user = await user_service.find_or_create_by_telegram_id(
        session, telegram_user_id, username, first_name
    )
    await session.commit()
    access_token = create_access_token(user.id)
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_expire_days * 86400,
    )
