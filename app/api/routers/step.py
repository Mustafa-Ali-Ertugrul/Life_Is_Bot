"""Step tracker settings and logs endpoints."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.api.rate_limit import CRUD_LIMIT, limiter
from app.api.schemas.step import (
    StepLogCreate,
    StepLogResponse,
    StepSettingsResponse,
    StepSettingsUpdate,
)
from app.core.errors import InvalidStateError, NotFoundError
from app.models import StepLog, StepSettings
from app.services import step_service

router = APIRouter(prefix="/api/step", tags=["step"])


@router.get("/settings", response_model=StepSettingsResponse)
@limiter.limit(CRUD_LIMIT)
async def get_step_settings(
    request: Request,
    response: Response,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> StepSettings:
    return await step_service.get_or_create_settings(session, user_id)


@router.patch("/settings", response_model=StepSettingsResponse)
@limiter.limit(CRUD_LIMIT)
async def update_step_settings(
    request: Request,
    response: Response,
    body: StepSettingsUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> StepSettings:
    return await step_service.update_settings(
        session, user_id, **body.model_dump(exclude_unset=True)
    )


@router.get("/logs", response_model=list[StepLogResponse])
@limiter.limit(CRUD_LIMIT)
async def list_step_logs(
    request: Request,
    response: Response,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    start: Annotated[date, Query()],
    end: Annotated[date, Query()],
) -> list[StepLog]:
    if start > end:
        raise InvalidStateError("start must not be after end")
    return await step_service.get_logs_range(session, user_id, start, end)


@router.post("/logs", response_model=StepLogResponse, status_code=201)
@limiter.limit(CRUD_LIMIT)
async def create_step_log(
    request: Request,
    response: Response,
    body: StepLogCreate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> StepLog:
    return await step_service.log_steps(session, user_id, steps=body.steps, log_date=body.log_date)


@router.get("/logs/{log_date}", response_model=StepLogResponse)
@limiter.limit(CRUD_LIMIT)
async def get_step_log(
    request: Request,
    response: Response,
    log_date: date,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> StepLog:
    log = await step_service.get_steps_for_date(session, user_id, log_date)
    if log is None:
        raise NotFoundError(f"StepLog for {log_date} not found")
    return log
