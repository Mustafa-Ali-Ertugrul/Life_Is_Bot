from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone import now_in
from app.models import BotKey, BotPreference

CORE_BOT_CANNOT_BE_DISABLED = "Ana bot kapatılamaz."


async def get_preference(
    session: AsyncSession, user_id: int, bot_key: BotKey
) -> BotPreference | None:
    result = await session.execute(
        select(BotPreference).where(
            BotPreference.user_id == user_id,
            BotPreference.bot_key == bot_key.value,
        )
    )
    return result.scalar_one_or_none()


async def get_or_create_preference(
    session: AsyncSession, user_id: int, bot_key: BotKey
) -> BotPreference:
    preference = await get_preference(session, user_id, bot_key)
    if preference is not None:
        return preference

    preference = BotPreference(
        user_id=user_id,
        bot_key=bot_key.value,
        enabled=False,
        settings_json="{}",
    )
    session.add(preference)
    await session.commit()
    await session.refresh(preference)
    return preference


async def list_preferences(session: AsyncSession, user_id: int) -> list[BotPreference]:
    result = await session.execute(
        select(BotPreference)
        .where(BotPreference.user_id == user_id)
        .order_by(BotPreference.bot_key)
    )
    return list(result.scalars().all())


async def toggle_preference(
    session: AsyncSession, user_id: int, bot_key: BotKey, enabled: bool
) -> BotPreference:
    if bot_key is BotKey.CORE:
        raise ValueError(CORE_BOT_CANNOT_BE_DISABLED)

    preference = await get_or_create_preference(session, user_id, bot_key)
    preference.enabled = enabled
    preference.updated_at = now_in("UTC")
    await session.commit()
    await session.refresh(preference)
    return preference
