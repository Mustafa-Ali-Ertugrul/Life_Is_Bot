"""FastAPI dependency injection."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, settings
from app.core.database import unit_of_work


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session with unit-of-work transaction boundary."""
    async with unit_of_work() as session:
        yield session


def get_settings() -> Settings:
    """Return application settings."""
    return settings
