import json
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import InvalidStateError, NotFoundError
from app.core.schedule import parse_days
from app.core.timezone import get_user_timezone, now_in, to_utc_scheduled
from app.models import BotKey, MedicationPlan, ReminderEvent, User
from app.services import preference_service, reminder_service

RELATED_TYPE = "medication_plan"

VALID_WITH_FOOD = {"empty", "full", "any"}

MAX_NOTES_LENGTH = 500


async def create_medication_plan(
    session: AsyncSession,
    user_id: int,
    name: str,
    target_hour: int,
    target_minute: int,
    days_of_week: str,
    *,
    dose: str | None = None,
    with_food: str = "any",
    start_date: date | None = None,
    end_date: date | None = None,
    notes: str | None = None,
) -> MedicationPlan:
    """Create a new medication plan and auto-activate the medication preference."""
    if not name or not name.strip():
        raise InvalidStateError("name must not be empty")
    if not 0 <= target_hour <= 23:
        raise InvalidStateError("target_hour must be between 0 and 23")
    if not 0 <= target_minute <= 59:
        raise InvalidStateError("target_minute must be between 0 and 59")
    with_food = with_food.strip().lower()
    if with_food not in VALID_WITH_FOOD:
        raise InvalidStateError(f"with_food must be one of {sorted(VALID_WITH_FOOD)}")
    if start_date is not None and end_date is not None and start_date > end_date:
        raise InvalidStateError("start_date must not be after end_date")
    if notes is not None and len(notes) > MAX_NOTES_LENGTH:
        raise InvalidStateError("notes must be at most 500 characters")

    plan = MedicationPlan(
        user_id=user_id,
        name=name.strip(),
        dose=dose.strip() if dose else None,
        with_food=with_food,
        target_hour=target_hour,
        target_minute=target_minute,
        days_of_week=days_of_week,
        start_date=start_date,
        end_date=end_date,
        is_active=True,
        notes=notes.strip() if notes else None,
    )
    session.add(plan)
    await session.commit()
    await session.refresh(plan)
    await preference_service.toggle_preference(session, user_id, BotKey.MEDICATION, enabled=True)
    return plan


async def list_medication_plans(
    session: AsyncSession, user_id: int, *, active_only: bool = False
) -> list[MedicationPlan]:
    stmt = select(MedicationPlan).where(MedicationPlan.user_id == user_id)
    if active_only:
        stmt = stmt.where(MedicationPlan.is_active.is_(True))
    stmt = stmt.order_by(MedicationPlan.target_hour, MedicationPlan.target_minute)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_medication_plan(session: AsyncSession, plan_id: int) -> MedicationPlan | None:
    result = await session.execute(select(MedicationPlan).where(MedicationPlan.id == plan_id))
    return result.scalar_one_or_none()


async def update_medication_plan(
    session: AsyncSession,
    plan_id: int,
    *,
    name: str | None = None,
    dose: str | None = None,
    with_food: str | None = None,
    target_hour: int | None = None,
    target_minute: int | None = None,
    days_of_week: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    notes: str | None = None,
) -> MedicationPlan:
    """Partially update a medication plan."""
    plan = await get_medication_plan(session, plan_id)
    if plan is None:
        raise NotFoundError(f"MedicationPlan {plan_id} not found")

    if name is not None:
        if not name.strip():
            raise InvalidStateError("name must not be empty")
        plan.name = name.strip()
    if dose is not None:
        plan.dose = dose.strip() if dose else None
    if with_food is not None:
        normalized = with_food.strip().lower()
        if normalized not in VALID_WITH_FOOD:
            raise InvalidStateError(f"with_food must be one of {sorted(VALID_WITH_FOOD)}")
        plan.with_food = normalized
    if target_hour is not None:
        if not 0 <= target_hour <= 23:
            raise InvalidStateError("target_hour must be between 0 and 23")
        plan.target_hour = target_hour
    if target_minute is not None:
        if not 0 <= target_minute <= 59:
            raise InvalidStateError("target_minute must be between 0 and 59")
        plan.target_minute = target_minute
    if days_of_week is not None:
        plan.days_of_week = days_of_week
    if start_date is not None:
        plan.start_date = start_date
    if end_date is not None:
        plan.end_date = end_date
    if notes is not None:
        if len(notes) > MAX_NOTES_LENGTH:
            raise InvalidStateError("notes must be at most 500 characters")
        plan.notes = notes.strip() if notes else None

    if (
        plan.start_date is not None
        and plan.end_date is not None
        and plan.start_date > plan.end_date
    ):
        raise InvalidStateError("start_date must not be after end_date")

    await session.commit()
    await session.refresh(plan)
    return plan


async def toggle_medication_plan(
    session: AsyncSession, plan_id: int, is_active: bool
) -> MedicationPlan:
    plan = await get_medication_plan(session, plan_id)
    if plan is None:
        raise NotFoundError(f"MedicationPlan {plan_id} not found")
    plan.is_active = is_active
    await session.commit()
    await session.refresh(plan)
    return plan


async def generate_today_events(
    session: AsyncSession, user_id: int, now: datetime | None = None
) -> list[ReminderEvent]:
    tz = get_user_timezone(await _user_timezone_name(session, user_id))
    base = now if now is not None else now_in()
    if base.tzinfo is None:
        base = base.replace(tzinfo=UTC)
    local_now = base.astimezone(tz)
    local_date = local_now.date()
    weekday = local_now.isoweekday()
    plans = await list_medication_plans(session, user_id)
    events: list[ReminderEvent] = []
    for plan in plans:
        if not plan.is_active:
            continue
        if plan.start_date is not None and local_date < plan.start_date:
            continue
        if plan.end_date is not None and local_date > plan.end_date:
            continue
        if weekday not in parse_days(plan.days_of_week):
            continue
        local_scheduled = local_now.replace(
            hour=plan.target_hour,
            minute=plan.target_minute,
            second=0,
            microsecond=0,
        )
        scheduled_at = to_utc_scheduled(local_scheduled)
        event = await reminder_service.create_event(
            session,
            user_id=user_id,
            bot_key=BotKey.MEDICATION,
            scheduled_at=scheduled_at,
            related_type=RELATED_TYPE,
            related_id=plan.id,
            interpretation_json=json.dumps(
                {
                    "name": plan.name,
                    "dose": plan.dose,
                    "with_food": plan.with_food,
                    "notes": plan.notes,
                    "target_hour": plan.target_hour,
                    "target_minute": plan.target_minute,
                },
                ensure_ascii=False,
            ),
        )
        events.append(event)
    return events


async def _user_timezone_name(session: AsyncSession, user_id: int) -> str:
    result = await session.execute(select(User.timezone).where(User.id == user_id))
    return result.scalar_one_or_none() or settings.timezone


__all__ = [
    "MAX_NOTES_LENGTH",
    "MedicationPlan",
    "RELATED_TYPE",
    "VALID_WITH_FOOD",
    "create_medication_plan",
    "generate_today_events",
    "get_medication_plan",
    "list_medication_plans",
    "toggle_medication_plan",
    "update_medication_plan",
]
