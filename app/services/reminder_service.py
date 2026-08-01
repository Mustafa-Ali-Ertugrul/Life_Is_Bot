from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.timezone import now_in
from app.models import BotKey, ReminderEvent, ReminderStatus, User, UserResponse

_WINDOW_DAYS = 1


async def create_event(
    session: AsyncSession,
    user_id: int,
    bot_key: BotKey,
    scheduled_at: datetime,
    related_type: str | None = None,
    related_id: int | None = None,
    interpretation_json: str = "{}",
) -> ReminderEvent:
    if related_type is not None and related_id is not None:
        existing = await _find_existing_event(
            session, user_id, related_type, related_id, scheduled_at
        )
        if existing is not None:
            return existing

    event = ReminderEvent(
        user_id=user_id,
        bot_key=bot_key.value,
        related_type=related_type,
        related_id=related_id,
        scheduled_at=scheduled_at,
        status=ReminderStatus.SCHEDULED.value,
        interpretation_json=interpretation_json,
        created_at=now_in(),
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event


async def _find_existing_event(
    session: AsyncSession,
    user_id: int,
    related_type: str,
    related_id: int,
    scheduled_at: datetime,
) -> ReminderEvent | None:
    start = scheduled_at.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=_WINDOW_DAYS)
    result = await session.execute(
        select(ReminderEvent).where(
            ReminderEvent.user_id == user_id,
            ReminderEvent.related_type == related_type,
            ReminderEvent.related_id == related_id,
            ReminderEvent.scheduled_at >= start,
            ReminderEvent.scheduled_at < end,
            ReminderEvent.status.in_(
                [ReminderStatus.SCHEDULED.value, ReminderStatus.NOTIFIED.value]
            ),
        )
    )
    return result.scalars().first()


async def get_event(session: AsyncSession, event_id: int) -> ReminderEvent | None:
    result = await session.execute(
        select(ReminderEvent)
        .where(ReminderEvent.id == event_id)
        .options(selectinload(ReminderEvent.user).selectinload(User.telegram_account))
    )
    return result.scalar_one_or_none()


async def find_due_events(
    session: AsyncSession, now: datetime, limit: int = 50
) -> list[ReminderEvent]:
    result = await session.execute(
        select(ReminderEvent)
        .where(
            ReminderEvent.status == ReminderStatus.SCHEDULED.value,
            ReminderEvent.notified_at.is_(None),
            ReminderEvent.scheduled_at <= now,
        )
        .options(selectinload(ReminderEvent.user).selectinload(User.telegram_account))
        .order_by(ReminderEvent.scheduled_at)
        .limit(limit)
    )
    return list(result.scalars().all())


async def mark_notified(session: AsyncSession, event_id: int) -> bool:
    result = await session.execute(
        update(ReminderEvent)
        .where(
            ReminderEvent.id == event_id,
            ReminderEvent.status == ReminderStatus.SCHEDULED.value,
        )
        .values(status=ReminderStatus.NOTIFIED.value, notified_at=now_in())
    )
    await session.commit()
    rowcount = result.rowcount  # type: ignore[attr-defined]
    return rowcount is not None and rowcount > 0


async def should_skip_notify(session: AsyncSession, event: ReminderEvent) -> bool:
    if event.status != ReminderStatus.SCHEDULED.value:
        return True
    if event.notified_at is not None:
        return True

    bot_key = BotKey(event.bot_key)
    from app.services.preference_service import get_preference

    preference = await get_preference(session, event.user_id, bot_key)
    if preference is None:
        return bot_key is not BotKey.CORE
    if not preference.enabled:
        return True

    responses = await _existing_responses(session, event.id)
    return len(responses) > 0


async def _existing_responses(session: AsyncSession, event_id: int) -> list[UserResponse]:
    result = await session.execute(
        select(UserResponse).where(
            UserResponse.reminder_event_id == event_id,
            UserResponse.is_current.is_(True),
        )
    )
    return list(result.scalars().all())


__all__ = [
    "ReminderEvent",
    "ReminderStatus",
    "User",
    "create_event",
    "find_due_events",
    "get_event",
    "mark_notified",
    "should_skip_notify",
]
