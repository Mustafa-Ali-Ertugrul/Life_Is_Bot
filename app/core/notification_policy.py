from datetime import UTC, datetime
from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.quiet_hours import is_within_quiet_hours, next_quiet_end
from app.core.timezone import get_user_timezone
from app.models import BotKey, ReminderEvent, ReminderStatus, User, UserResponse
from app.services.preference_service import get_preference


class NotificationDecision(TypedDict):
    action: str
    reason: str
    defer_until: datetime | None


async def evaluate_notification(
    session: AsyncSession,
    user: User,
    event: ReminderEvent,
    now: datetime,
) -> NotificationDecision:
    if event.status != ReminderStatus.SCHEDULED.value:
        return NotificationDecision(action="suppress", reason="not_scheduled", defer_until=None)
    if event.notified_at is not None:
        return NotificationDecision(action="suppress", reason="already_notified", defer_until=None)
    if not user.is_active:
        return NotificationDecision(action="suppress", reason="user_inactive", defer_until=None)
    if not user.consent_given:
        return NotificationDecision(action="suppress", reason="consent_missing", defer_until=None)
    if not user.notifications_enabled:
        return NotificationDecision(
            action="suppress", reason="notifications_disabled", defer_until=None
        )

    bot_key = BotKey(event.bot_key)
    preference = await get_preference(session, user.id, bot_key)
    if preference is None:
        if bot_key is not BotKey.CORE:
            return NotificationDecision(action="suppress", reason="bot_disabled", defer_until=None)
    elif not preference.enabled:
        return NotificationDecision(action="suppress", reason="bot_disabled", defer_until=None)

    if await _has_current_response(session, event.id):
        return NotificationDecision(action="suppress", reason="already_responded", defer_until=None)

    if (
        user.quiet_hours_enabled
        and user.quiet_hours_start is not None
        and user.quiet_hours_end is not None
    ):
        local_now = now.astimezone(get_user_timezone(user.timezone))
        if is_within_quiet_hours(local_now, user.quiet_hours_start, user.quiet_hours_end):
            defer_until = next_quiet_end(local_now, user.quiet_hours_start, user.quiet_hours_end)
            return NotificationDecision(
                action="defer",
                reason="quiet_hours",
                defer_until=defer_until.astimezone(UTC),
            )

    return NotificationDecision(action="send_now", reason="ok", defer_until=None)


async def _has_current_response(session: AsyncSession, event_id: int) -> bool:
    result = await session.execute(
        select(UserResponse.id).where(
            UserResponse.reminder_event_id == event_id,
            UserResponse.is_current.is_(True),
        )
    )
    return result.scalars().first() is not None


__all__ = ["NotificationDecision", "evaluate_notification"]
