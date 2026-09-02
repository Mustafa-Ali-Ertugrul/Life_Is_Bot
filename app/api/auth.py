"""Authentication primitives: JWT issuance and provisioning key verification."""

import hashlib
import hmac
import json
import urllib.parse
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.config import settings

JWT_ALGORITHM = "HS256"
TELEGRAM_INITDATA_MAX_AGE_SECONDS = 86400


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


def verify_telegram_init_data(init_data: str) -> dict[str, Any]:
    """Validate Telegram WebApp initData and return parsed fields.

    Implements https://core.telegram.org/bots/web_apps#validating-data-received-via-the-mini-app.
    Raises AuthError if validation fails or data is expired.
    """
    if not settings.bot_token:
        raise AuthError("bot token not configured for initData verification")
    if not init_data:
        raise AuthError("empty initData")
    try:
        parsed = dict(urllib.parse.parse_qsl(init_data, strict_parsing=False))
    except ValueError as exc:
        raise AuthError("invalid initData encoding") from exc
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise AuthError("initData missing hash")
    check_parts = [f"{k}={v}" for k, v in sorted(parsed.items())]
    data_check_string = "\n".join(check_parts)
    secret_key = hmac.new(b"WebAppData", settings.bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed_hash, received_hash):
        raise AuthError("initData hash mismatch")
    auth_date_raw = parsed.get("auth_date")
    if auth_date_raw:
        try:
            auth_date = int(auth_date_raw)
            now_ts = int(datetime.now(UTC).timestamp())
            if abs(now_ts - auth_date) > TELEGRAM_INITDATA_MAX_AGE_SECONDS:
                raise AuthError("initData expired")
        except ValueError as exc:
            raise AuthError("invalid auth_date") from exc
    user_json = parsed.get("user")
    if user_json:
        try:
            parsed["user_dict"] = json.loads(user_json)
        except json.JSONDecodeError as exc:
            raise AuthError("invalid user payload") from exc
    return parsed
