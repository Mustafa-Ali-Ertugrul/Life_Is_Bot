"""Supplement plan CRUD endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, pagination_params
from app.api.schemas.pagination import PaginatedResponse, paginate
from app.api.schemas.supplement import SupplementCreate, SupplementResponse, SupplementUpdate
from app.core.errors import NotFoundError
from app.models import SupplementPlan
from app.services import supplement_service

router = APIRouter(prefix="/api/supplement", tags=["supplement"])


async def _get_owned_plan(session: AsyncSession, plan_id: int, user_id: int) -> SupplementPlan:
    plan = await supplement_service.get_supplement_plan(session, plan_id)
    if plan is None or plan.user_id != user_id:
        raise NotFoundError(f"SupplementPlan {plan_id} not found")
    return plan


@router.get("", response_model=PaginatedResponse[SupplementResponse])
async def list_supplement_plans(
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[tuple[int, int], Depends(pagination_params)],
) -> PaginatedResponse[SupplementResponse]:
    plans = await supplement_service.list_supplement_plans(session, user_id)
    limit, offset = pagination
    return paginate([SupplementResponse.model_validate(plan) for plan in plans], limit, offset)


@router.post("", response_model=SupplementResponse, status_code=201)
async def create_supplement_plan(
    body: SupplementCreate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SupplementPlan:
    return await supplement_service.create_supplement_plan(
        session,
        user_id,
        name=body.name,
        days_of_week=body.days_of_week,
        target_hour=body.target_hour,
        target_minute=body.target_minute,
        dose=body.dose,
        with_food=body.with_food,
        start_date=body.start_date,
        end_date=body.end_date,
    )


@router.get("/{plan_id}", response_model=SupplementResponse)
async def get_supplement_plan(
    plan_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SupplementPlan:
    return await _get_owned_plan(session, plan_id, user_id)


@router.patch("/{plan_id}", response_model=SupplementResponse)
async def update_supplement_plan(
    plan_id: int,
    body: SupplementUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SupplementPlan:
    await _get_owned_plan(session, plan_id, user_id)
    return await supplement_service.update_supplement_plan(
        session, plan_id, **body.model_dump(exclude_unset=True)
    )


@router.delete("/{plan_id}", status_code=204)
async def delete_supplement_plan(
    plan_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await _get_owned_plan(session, plan_id, user_id)
    await supplement_service.toggle_supplement_plan(session, plan_id, is_active=False)
