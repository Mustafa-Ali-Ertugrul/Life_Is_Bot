"""Device token provisioning endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import create_access_token, verify_provisioning_key
from app.api.deps import get_db, resolve_first_user_id
from app.api.schemas.auth import TokenResponse
from app.core.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/token", response_model=TokenResponse)
async def issue_token(
    session: Annotated[AsyncSession, Depends(get_db)],
    x_provisioning_key: Annotated[str | None, Header()] = None,
) -> TokenResponse:
    """Exchange the provisioning key for a long-lived device JWT."""
    if not x_provisioning_key or not verify_provisioning_key(x_provisioning_key):
        raise HTTPException(status_code=401, detail="invalid provisioning key")
    user_id = await resolve_first_user_id(session)
    access_token = create_access_token(user_id)
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_expire_days * 86400,
    )
