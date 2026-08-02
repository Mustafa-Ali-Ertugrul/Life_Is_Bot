from datetime import UTC, date, datetime

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.timezone import get_user_timezone, now_in
from app.models import BotKey, ReminderEvent, ReminderStatus, User


def _canonical_utc(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(UTC)
    return value


def build_reminder_dedupe_key(
    bot_key: str,
    related_type: str | None,
    related_id: int | None,
    scheduled_local_date: date,
) -> str:
    return (
        f"{bot_key}:{related_type or 'none'}:{related_id or 0}:{scheduled_local_date.isoformat()}"
    )


async def create_event(
    session: AsyncSession,
    user_id: int,
    bot_key: BotKey,
    scheduled_at: datetime,
    related_type: str | None = None,
    related_id: int | None = None,
    interpretation_json: str = "{}",
) -> ReminderEvent:
    scheduled_at = _canonical_utc(scheduled_at)
    scheduled_local_date = await _scheduled_local_date(session, user_id, scheduled_at)
    dedupe_key = build_reminder_dedupe_key(
        bot_key.value, related_type, related_id, scheduled_local_date
    )

    existing = await _find_by_dedupe(session, user_id, dedupe_key)
    if existing is not None:
        if existing.status == ReminderStatus.CANCELLED.value:
            return await _reactivate(session, existing, scheduled_at)
        return existing

    event = ReminderEvent(
        user_id=user_id,
        bot_key=bot_key.value,
        related_type=related_type,
        related_id=related_id,
        scheduled_at=scheduled_at,
        scheduled_local_date=scheduled_local_date,
        dedupe_key=dedupe_key,
        status=ReminderStatus.SCHEDULED.value,
        interpretation_json=interpretation_json,
        created_at=now_in("UTC"),
    )
    try:
        async with session.begin_nested():
            session.add(event)
            await session.flush()
    except IntegrityError:
        existing = await _find_by_dedupe(session, user_id, dedupe_key)
        if existing is not None:
            if existing.status == ReminderStatus.CANCELLED.value:
                return await _reactivate(session, existing, scheduled_at)
            return existing
        raise
    await session.refresh(event)
    return event


async def reschedule_event(
    session: AsyncSession, event_id: int, new_scheduled_at: datetime
) -> ReminderEvent | None:
    event = await session.get(ReminderEvent, event_id)
    if event is None:
        return None
    try:
        async with session.begin_nested():
            return await _reactivate(session, event, new_scheduled_at)
    except IntegrityError:
        return None


async def _reactivate(
    session: AsyncSession, event: ReminderEvent, scheduled_at: datetime
) -> ReminderEvent:
    scheduled_at = _canonical_utc(scheduled_at)
    scheduled_local_date = await _scheduled_local_date(session, event.user_id, scheduled_at)
    event.scheduled_at = scheduled_at
    event.scheduled_local_date = scheduled_local_date
    event.dedupe_key = build_reminder_dedupe_key(
        event.bot_key, event.related_type, event.related_id, scheduled_local_date
    )
    event.status = ReminderStatus.SCHEDULED.value
    event.notified_at = None
    await session.flush()
    await session.refresh(event)
    return event


async def _find_by_dedupe(
    session: AsyncSession, user_id: int, dedupe_key: str
) -> ReminderEvent | None:
    result = await session.execute(
        select(ReminderEvent).where(
            ReminderEvent.user_id == user_id,
            ReminderEvent.dedupe_key == dedupe_key,
        )
    )
    return result.scalars().first()


async def _scheduled_local_date(
    session: AsyncSession, user_id: int, scheduled_at: datetime
) -> date:
    local = _canonical_utc(scheduled_at)
    tz_name = await _user_timezone_name(session, user_id)
    return local.astimezone(get_user_timezone(tz_name)).date()


async def _user_timezone_name(session: AsyncSession, user_id: int) -> str:
    result = await session.execute(select(User.timezone).where(User.id == user_id))
    return result.scalar_one_or_none() or settings.timezone


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
    now = _canonical_utc(now)
    result = await session.execute(
        select(ReminderEvent)
        .where(
            ReminderEvent.status == ReminderStatus.SCHEDULED.value,
            ReminderEvent.notified_at.is_(None),
            ReminderEvent.scheduled_at <= now,
            or_(
                ReminderEvent.notify_after.is_(None),
                ReminderEvent.notify_after <= now,
            ),
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
        .values(status=ReminderStatus.NOTIFIED.value, notified_at=now_in("UTC"))
    )
    await session.flush()
    rowcount = result.rowcount  # type: ignore[attr-defined]
    return rowcount is not None and rowcount > 0


async def mark_suppressed(session: AsyncSession, event_id: int) -> bool:
    result = await session.execute(
        update(ReminderEvent)
        .where(
            ReminderEvent.id == event_id,
            ReminderEvent.status == ReminderStatus.SCHEDULED.value,
        )
        .values(status=ReminderStatus.SUPPRESSED.value)
    )
    await session.flush()
    rowcount = result.rowcount  # type: ignore[attr-defined]
    return rowcount is not None and rowcount > 0


__all__ = [
    "ReminderEvent",
    "ReminderStatus",
    "User",
    "build_reminder_dedupe_key",
    "create_event",
    "find_due_events",
    "get_event",
    "mark_notified",
    "mark_suppressed",
    "reschedule_event",
]
