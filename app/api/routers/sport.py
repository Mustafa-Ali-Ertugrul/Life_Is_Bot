"""Sport plan CRUD endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, pagination_params
from app.api.rate_limit import CRUD_LIMIT, limiter
from app.api.schemas.pagination import PaginatedResponse, paginate
from app.api.schemas.sport import SportCreate, SportResponse, SportUpdate
from app.core.errors import NotFoundError
from app.models import SportPlan
from app.services import sport_service

router = APIRouter(prefix="/api/sport", tags=["sport"])


async def _get_owned_plan(session: AsyncSession, plan_id: int, user_id: int) -> SportPlan:
    plan = await sport_service.get_sport_plan(session, plan_id)
    if plan is None or plan.user_id != user_id:
        raise NotFoundError(f"SportPlan {plan_id} not found")
    return plan


@router.get("", response_model=PaginatedResponse[SportResponse])
@limiter.limit(CRUD_LIMIT)
async def list_sport_plans(
    request: Request,
    response: Response,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[tuple[int, int], Depends(pagination_params)],
) -> PaginatedResponse[SportResponse]:
    plans = await sport_service.list_sport_plans(session, user_id)
    limit, offset = pagination
    return paginate([SportResponse.model_validate(plan) for plan in plans], limit, offset)


@router.post("", response_model=SportResponse, status_code=201)
@limiter.limit(CRUD_LIMIT)
async def create_sport_plan(
    request: Request,
    response: Response,
    body: SportCreate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SportPlan:
    return await sport_service.create_sport_plan(
        session,
        user_id,
        sport_type=body.sport_type,
        days_of_week=body.days_of_week,
        target_hour=body.target_hour,
        target_minute=body.target_minute,
    )


@router.get("/{plan_id}", response_model=SportResponse)
@limiter.limit(CRUD_LIMIT)
async def get_sport_plan(
    request: Request,
    response: Response,
    plan_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SportPlan:
    return await _get_owned_plan(session, plan_id, user_id)


@router.patch("/{plan_id}", response_model=SportResponse)
@limiter.limit(CRUD_LIMIT)
async def update_sport_plan(
    request: Request,
    response: Response,
    plan_id: int,
    body: SportUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SportPlan:
    await _get_owned_plan(session, plan_id, user_id)
    return await sport_service.update_sport_plan(
        session, plan_id, **body.model_dump(exclude_unset=True)
    )


@router.delete("/{plan_id}", status_code=204)
@limiter.limit(CRUD_LIMIT)
async def delete_sport_plan(
    request: Request,
    response: Response,
    plan_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await _get_owned_plan(session, plan_id, user_id)
    await sport_service.toggle_sport_plan(session, plan_id, is_active=False)
