"""Medication plan CRUD endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, pagination_params
from app.api.schemas.medication import MedicationCreate, MedicationResponse, MedicationUpdate
from app.api.schemas.pagination import PaginatedResponse, paginate
from app.core.errors import NotFoundError
from app.models import MedicationPlan
from app.services import medication_service

router = APIRouter(prefix="/api/medications", tags=["medications"])


async def _get_owned_plan(session: AsyncSession, plan_id: int, user_id: int) -> MedicationPlan:
    plan = await medication_service.get_medication_plan(session, plan_id)
    if plan is None or plan.user_id != user_id:
        raise NotFoundError(f"MedicationPlan {plan_id} not found")
    return plan


@router.get("", response_model=PaginatedResponse[MedicationResponse])
async def list_medications(
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[tuple[int, int], Depends(pagination_params)],
) -> PaginatedResponse[MedicationResponse]:
    plans = await medication_service.list_medication_plans(session, user_id)
    limit, offset = pagination
    return paginate([MedicationResponse.model_validate(plan) for plan in plans], limit, offset)


@router.post("", response_model=MedicationResponse, status_code=201)
async def create_medication(
    body: MedicationCreate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MedicationPlan:
    return await medication_service.create_medication_plan(
        session,
        user_id,
        name=body.name,
        target_hour=body.target_hour,
        target_minute=body.target_minute,
        days_of_week=body.days_of_week,
        dose=body.dose,
        with_food=body.with_food,
        start_date=body.start_date,
        end_date=body.end_date,
        notes=body.notes,
    )


@router.get("/{plan_id}", response_model=MedicationResponse)
async def get_medication(
    plan_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MedicationPlan:
    return await _get_owned_plan(session, plan_id, user_id)


@router.patch("/{plan_id}", response_model=MedicationResponse)
async def update_medication(
    plan_id: int,
    body: MedicationUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MedicationPlan:
    await _get_owned_plan(session, plan_id, user_id)
    return await medication_service.update_medication_plan(
        session, plan_id, **body.model_dump(exclude_unset=True)
    )


@router.delete("/{plan_id}", status_code=204)
async def delete_medication(
    plan_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await _get_owned_plan(session, plan_id, user_id)
    await medication_service.toggle_medication_plan(session, plan_id, is_active=False)
