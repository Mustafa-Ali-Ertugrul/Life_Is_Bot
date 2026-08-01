from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone import now_in
from app.models import BotKey, ReminderEvent, ReminderStatus, ResponseType, UserResponse


async def save_response(
    session: AsyncSession,
    reminder_event_id: int,
    user_id: int,
    bot_key: BotKey,
    response: ResponseType,
    reason: str | None = None,
    source: str = "telegram_inline",
) -> UserResponse:
    await session.execute(
        update(UserResponse)
        .where(
            UserResponse.reminder_event_id == reminder_event_id,
            UserResponse.is_current.is_(True),
        )
        .values(is_current=False)
    )

    new_response = UserResponse(
        reminder_event_id=reminder_event_id,
        user_id=user_id,
        bot_key=bot_key.value,
        response=response.value,
        reason=reason,
        source=source,
        responded_at=now_in(),
        is_current=True,
    )
    session.add(new_response)
    await session.flush()

    status = _map_response_to_status(response)
    await session.execute(
        update(ReminderEvent).where(ReminderEvent.id == reminder_event_id).values(status=status)
    )
    await session.commit()
    await session.refresh(new_response)
    return new_response


async def get_current_responses(
    session: AsyncSession, reminder_event_id: int
) -> list[UserResponse]:
    result = await session.execute(
        select(UserResponse).where(
            UserResponse.reminder_event_id == reminder_event_id,
            UserResponse.is_current.is_(True),
        )
    )
    return list(result.scalars().all())


def _map_response_to_status(response: ResponseType) -> str:
    positive = {
        ResponseType.DONE,
        ResponseType.TAKEN,
        ResponseType.YES,
    }
    negative = {
        ResponseType.NOT_DONE,
        ResponseType.NOT_TAKEN,
        ResponseType.NO,
    }
    if response in positive:
        return ReminderStatus.POSITIVE.value
    if response in negative:
        return ReminderStatus.NEGATIVE.value
    if response is ResponseType.PARTIAL:
        return ReminderStatus.POSITIVE.value
    if response is ResponseType.SNOOZED:
        return ReminderStatus.SNOOZED.value
    return ReminderStatus.NO_RESPONSE.value
