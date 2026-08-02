import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.schedule import parse_days
from app.core.timezone import get_user_timezone, now_in, to_utc_scheduled
from app.models import BotKey, ReminderEvent, ReminderStatus, SportPlan, User
from app.services import preference_service, reminder_service

RELATED_TYPE = "sport_plan"


async def create_sport_plan(
    session: AsyncSession,
    user_id: int,
    sport_type: str,
    days_of_week: str,
    target_hour: int,
    target_minute: int,
) -> SportPlan:
    plan = SportPlan(
        user_id=user_id,
        sport_type=sport_type.strip(),
        target_hour=target_hour,
        target_minute=target_minute,
        days_of_week=days_of_week,
        is_active=True,
    )
    session.add(plan)
    await session.flush()
    await session.refresh(plan)
    await preference_service.toggle_preference(session, user_id, BotKey.SPORT, enabled=True)
    return plan


async def list_sport_plans(session: AsyncSession, user_id: int) -> list[SportPlan]:
    result = await session.execute(
        select(SportPlan).where(SportPlan.user_id == user_id).order_by(SportPlan.created_at)
    )
    return list(result.scalars().all())


async def get_sport_plan(session: AsyncSession, plan_id: int) -> SportPlan | None:
    result = await session.execute(select(SportPlan).where(SportPlan.id == plan_id))
    return result.scalar_one_or_none()


async def toggle_sport_plan(
    session: AsyncSession, plan_id: int, is_active: bool
) -> SportPlan | None:
    plan = await get_sport_plan(session, plan_id)
    if plan is None:
        return None
    plan.is_active = is_active
    await session.flush()
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
    weekday = local_now.isoweekday()
    plans = await list_sport_plans(session, user_id)
    events: list[ReminderEvent] = []
    for plan in plans:
        if not plan.is_active:
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
            bot_key=BotKey.SPORT,
            scheduled_at=scheduled_at,
            related_type=RELATED_TYPE,
            related_id=plan.id,
            interpretation_json=json.dumps(
                {
                    "sport_type": plan.sport_type,
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


async def get_completion_stats(
    session: AsyncSession, user_id: int, days: int = 7, now: datetime | None = None
) -> dict[str, int]:
    since = (now if now is not None else now_in("UTC")) - timedelta(days=days)
    result = await session.execute(
        select(ReminderEvent).where(
            ReminderEvent.user_id == user_id,
            ReminderEvent.related_type == RELATED_TYPE,
            ReminderEvent.scheduled_at >= since,
        )
    )
    events = list(result.scalars().all())
    total = len(events)
    completed = sum(1 for e in events if e.status == ReminderStatus.POSITIVE.value)
    return {"total": total, "completed": completed}


__all__ = [
    "RELATED_TYPE",
    "SportPlan",
    "create_sport_plan",
    "generate_today_events",
    "get_completion_stats",
    "get_sport_plan",
    "list_sport_plans",
    "toggle_sport_plan",
]
