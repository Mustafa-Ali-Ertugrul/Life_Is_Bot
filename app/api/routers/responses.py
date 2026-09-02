"""Mobile notification response endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.api.rate_limit import CRUD_LIMIT, limiter
from app.api.schemas.response import ResponseCreate, ResponseOut
from app.core.errors import InvalidStateError, NotFoundError
from app.core.timezone import now_in
from app.modules.registry import get_module_by_related_type
from app.services import reminder_service, response_service

router = APIRouter(prefix="/api/responses", tags=["responses"])


@router.post("", response_model=ResponseOut, status_code=201)
@limiter.limit(CRUD_LIMIT)
async def submit_response(
    request: Request,
    response: Response,
    body: ResponseCreate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseOut:
    module = get_module_by_related_type(body.related_type)
    if module is None:
        raise NotFoundError(f"related_type bilinmiyor: {body.related_type}")

    event = await reminder_service.create_event(
        session,
        user_id,
        module.bot_key,
        scheduled_at=now_in("UTC"),
        related_type=body.related_type,
        related_id=body.related_id,
    )
    saved = await response_service.save_response(
        session,
        event.id,
        user_id,
        module.bot_key,
        body.response,
        source="mobile_app",
    )
    refreshed = await reminder_service.get_event(session, event.id)
    if refreshed is None:
        raise InvalidStateError("Event bulunamadı")
    return ResponseOut(
        event_id=refreshed.id,
        status=refreshed.status,
        response=saved.response,
        source=saved.source,
    )
