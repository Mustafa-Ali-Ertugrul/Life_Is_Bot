"""Per-user API rate limiting backed by slowapi."""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.core.config import settings


def _key_func(request: Request) -> str:
    """Rate limit key: authenticated user id, or client IP as fallback."""
    user_id = getattr(request.state, "user_id", None)
    if user_id is not None:
        return f"user:{user_id}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(
    key_func=_key_func,
    headers_enabled=True,
    storage_uri=settings.rate_limit_storage_uri,
    enabled=settings.rate_limit_enabled,
)

CRUD_LIMIT = f"{settings.rate_limit_crud_per_minute}/minute"
REPORTS_LIMIT = f"{settings.rate_limit_reports_per_minute}/minute"

__all__ = ["CRUD_LIMIT", "REPORTS_LIMIT", "limiter"]
