"""Habits CRUD endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, pagination_params
from app.api.schemas.habit import HabitCreate, HabitResponse, HabitUpdate
from app.api.schemas.pagination import PaginatedResponse, paginate
from app.core.errors import NotFoundError
from app.models import Habit
from app.services import habit_service

router = APIRouter(prefix="/api/habits", tags=["habits"])


async def _get_owned_habit(session: AsyncSession, habit_id: int, user_id: int) -> Habit:
    habit = await habit_service.get_habit(session, habit_id)
    if habit is None or habit.user_id != user_id:
        raise NotFoundError(f"Habit {habit_id} not found")
    return habit


@router.get("", response_model=PaginatedResponse[HabitResponse])
async def list_habits(
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[tuple[int, int], Depends(pagination_params)],
) -> PaginatedResponse[HabitResponse]:
    habits = await habit_service.list_habits(session, user_id)
    limit, offset = pagination
    return paginate([HabitResponse.model_validate(habit) for habit in habits], limit, offset)


@router.post("", response_model=HabitResponse, status_code=201)
async def create_habit(
    body: HabitCreate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Habit:
    return await habit_service.create_habit(
        session,
        user_id,
        name=body.name,
        target_hour=body.target_hour,
        target_minute=body.target_minute,
        days_of_week=body.days_of_week,
    )


@router.get("/{habit_id}", response_model=HabitResponse)
async def get_habit(
    habit_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Habit:
    return await _get_owned_habit(session, habit_id, user_id)


@router.patch("/{habit_id}", response_model=HabitResponse)
async def update_habit(
    habit_id: int,
    body: HabitUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Habit:
    await _get_owned_habit(session, habit_id, user_id)
    return await habit_service.update_habit(
        session, habit_id, **body.model_dump(exclude_unset=True)
    )


@router.delete("/{habit_id}", status_code=204)
async def delete_habit(
    habit_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await _get_owned_habit(session, habit_id, user_id)
    await habit_service.toggle_habit(session, habit_id, is_active=False)
