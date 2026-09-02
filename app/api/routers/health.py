"""Health check endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import API_VERSION
from app.api.deps import get_db
from app.api.schemas.health import HealthResponse
from app.core.logger import get_logger

logger = get_logger("api.health")

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
@router.get("/api/health", response_model=HealthResponse)
async def health(db: Annotated[AsyncSession, Depends(get_db)]) -> HealthResponse:
    """Return service health and database connectivity."""
    try:
        await db.execute(text("SELECT 1"))
        database_ok = True
    except Exception:
        logger.exception("health check database failure")
        database_ok = False
    return HealthResponse(status="ok", database=database_ok, version=API_VERSION)
