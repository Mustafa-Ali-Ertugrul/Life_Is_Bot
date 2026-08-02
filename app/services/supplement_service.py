import json
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import InvalidStateError
from app.core.schedule import parse_days
from app.core.timezone import get_user_timezone, now_in, to_utc_scheduled
from app.models import BotKey, ReminderEvent, SupplementPlan, User
from app.services import preference_service, reminder_service

RELATED_TYPE = "supplement_plan"

VALID_WITH_FOOD = {"empty", "full", "any"}


async def create_supplement_plan(
    session: AsyncSession,
    user_id: int,
    name: str,
    days_of_week: str,
    target_hour: int,
    target_minute: int,
    *,
    dose: str | None = None,
    with_food: str = "any",
    start_date: date | None = None,
    end_date: date | None = None,
) -> SupplementPlan:
    with_food = with_food.strip().lower()
    if with_food not in VALID_WITH_FOOD:
        raise InvalidStateError(f"with_food must be one of {sorted(VALID_WITH_FOOD)}")
    if start_date is not None and end_date is not None and start_date > end_date:
        raise InvalidStateError("start_date must not be after end_date")
    plan = SupplementPlan(
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
    )
    session.add(plan)
    await session.commit()
    await session.refresh(plan)
    await preference_service.toggle_preference(session, user_id, BotKey.SUPPLEMENT, enabled=True)
    return plan


async def list_supplement_plans(session: AsyncSession, user_id: int) -> list[SupplementPlan]:
    result = await session.execute(
        select(SupplementPlan)
        .where(SupplementPlan.user_id == user_id)
        .order_by(SupplementPlan.created_at)
    )
    return list(result.scalars().all())


async def get_supplement_plan(session: AsyncSession, plan_id: int) -> SupplementPlan | None:
    result = await session.execute(select(SupplementPlan).where(SupplementPlan.id == plan_id))
    return result.scalar_one_or_none()


async def toggle_supplement_plan(
    session: AsyncSession, plan_id: int, is_active: bool
) -> SupplementPlan | None:
    plan = await get_supplement_plan(session, plan_id)
    if plan is None:
        return None
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
    plans = await list_supplement_plans(session, user_id)
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
            bot_key=BotKey.SUPPLEMENT,
            scheduled_at=scheduled_at,
            related_type=RELATED_TYPE,
            related_id=plan.id,
            interpretation_json=json.dumps(
                {
                    "name": plan.name,
                    "dose": plan.dose,
                    "with_food": plan.with_food,
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
    "RELATED_TYPE",
    "SupplementPlan",
    "VALID_WITH_FOOD",
    "create_supplement_plan",
    "generate_today_events",
    "get_supplement_plan",
    "list_supplement_plans",
    "toggle_supplement_plan",
]
