"""Bot preferences API router for enabling/disabling modules."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.api.rate_limit import CRUD_LIMIT, limiter
from app.models import BotKey
from app.services import preference_service

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


class BotPreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    bot_key: str
    enabled: bool


class BotPreferenceUpdate(BaseModel):
    enabled: bool


@router.get("", response_model=list[BotPreferenceResponse])
@limiter.limit(CRUD_LIMIT)
async def list_preferences(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[int, Depends(get_current_user)],
) -> list[BotPreferenceResponse]:
    """Get all bot preferences for current user."""
    preferences = []
    for bot_key in BotKey:
        if bot_key == BotKey.CORE:
            continue
        pref = await preference_service.get_or_create_preference(db, user_id, bot_key)
        preferences.append(pref)
    await db.commit()
    return [
        BotPreferenceResponse(bot_key=p.bot_key, enabled=p.enabled)
        for p in preferences
    ]


@router.patch("/{bot_key}", response_model=BotPreferenceResponse)
@limiter.limit(CRUD_LIMIT)
async def toggle_preference(
    bot_key: str,
    body: BotPreferenceUpdate,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[int, Depends(get_current_user)],
) -> BotPreferenceResponse:
    """Enable or disable a specific bot module."""
    try:
        key_enum = BotKey(bot_key)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid bot_key: {bot_key}")

    pref = await preference_service.toggle_preference(
        db, user_id, key_enum, body.enabled
    )
    await db.commit()
    return BotPreferenceResponse(bot_key=pref.bot_key, enabled=pref.enabled)
