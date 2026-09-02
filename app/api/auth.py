"""Authentication primitives: JWT issuance and provisioning key verification."""

import hmac
from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import settings

JWT_ALGORITHM = "HS256"


class AuthError(Exception):
    """Authentication failure."""


def create_access_token(user_id: int, *, expires_days: int | None = None) -> str:
    """Create a signed HS256 JWT for a user."""
    if not settings.jwt_secret:
        raise AuthError("JWT secret not configured")
    now = datetime.now(UTC)
    expire_days = expires_days or settings.jwt_expire_days
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(days=expire_days),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> int:
    """Decode and validate a JWT, returning the authenticated user id."""
    if not settings.jwt_secret:
        raise AuthError("JWT secret not configured")
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise AuthError("invalid token") from exc
    try:
        return int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise AuthError("invalid token subject") from None


def verify_api_key(api_key: str) -> bool:
    """Verify a static API key (legacy provisioning fallback)."""
    candidates = [
        candidate for candidate in (settings.api_key, settings.api_key_fallback) if candidate
    ]
    if not candidates:
        return False
    return any(hmac.compare_digest(api_key, candidate) for candidate in candidates)


def verify_provisioning_key(key: str) -> bool:
    """Verify a device provisioning key, falling back to static API keys."""
    if settings.provisioning_key and hmac.compare_digest(key, settings.provisioning_key):
        return True
    return verify_api_key(key)
