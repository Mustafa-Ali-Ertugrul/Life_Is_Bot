from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger("core.runtime")


def validate_startup_env() -> None:
    if not settings.bot_token:
        raise RuntimeError(
            "BOT_TOKEN boş. Lütfen .env dosyasına BotFather'dan aldığın token'ı yaz."
        )
    if not settings.database_url:
        raise ValueError("DATABASE_URL boş olamaz.")
    try:
        ZoneInfo(settings.timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Geçersiz timezone: {settings.timezone!r}") from exc


async def check_database(factory: async_sessionmaker[AsyncSession]) -> None:
    try:
        async with factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        raise RuntimeError("Veritabanı bağlantısı kurulamadı.") from exc
    logger.info("database connection ok")
