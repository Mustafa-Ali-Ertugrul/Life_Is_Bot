from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PermissionDeniedError
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


async def is_enabled(session: AsyncSession, user_id: int, bot_key: BotKey) -> bool:
    preference = await get_preference(session, user_id, bot_key)
    if preference is None:
        return bot_key is BotKey.CORE
    return preference.enabled


async def get_enabled_map(
    session: AsyncSession,
    user_ids: Sequence[int],
    bot_keys: Sequence[BotKey] | None = None,
) -> dict[tuple[int, str], bool]:
    """Kullanıcı-bot çiftleri için enabled durumlarını tek sorguda döndürür."""
    statement = select(BotPreference).where(BotPreference.user_id.in_(user_ids))
    if bot_keys is not None:
        statement = statement.where(
            BotPreference.bot_key.in_([bot_key.value for bot_key in bot_keys])
        )
    result = await session.execute(statement)
    return {
        (preference.user_id, preference.bot_key): preference.enabled
        for preference in result.scalars().all()
    }


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
        raise PermissionDeniedError(CORE_BOT_CANNOT_BE_DISABLED)

    preference = await get_or_create_preference(session, user_id, bot_key)
    preference.enabled = enabled
    preference.updated_at = now_in("UTC")
    await session.commit()
    await session.refresh(preference)
    return preference
