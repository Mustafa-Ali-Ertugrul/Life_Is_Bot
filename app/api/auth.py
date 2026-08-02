"""Telegram WebApp initData authentication."""

import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import parse_qs

from app.core.config import settings


class AuthError(Exception):
    """Authentication failure."""


def verify_telegram_init_data(init_data: str) -> dict[str, Any]:
    """Verify Telegram WebApp initData and return the parsed user object.

    Canonical algorithm:
    1. Parse the query string (values are percent-decoded once)
    2. Remove 'hash'
    3. data_check_string = sorted key=value pairs joined by newline
    4. secret_key = HMAC-SHA256("WebAppData", bot_token)
    5. computed_hash = HMAC-SHA256(secret_key, data_check_string)
    6. Constant-time comparison with the provided hash
    """
    flat = {k: v[0] for k, v in parse_qs(init_data, keep_blank_values=True).items()}

    provided_hash = flat.pop("hash", None)
    if not provided_hash:
        raise AuthError("missing hash")

    raw_auth_date = flat.get("auth_date")
    if raw_auth_date is None:
        raise AuthError("missing auth_date")
    try:
        auth_date = int(raw_auth_date)
    except ValueError:
        raise AuthError("invalid auth_date") from None
    if time.time() - auth_date > settings.api_auth_max_age:
        raise AuthError("initData expired")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(flat.items()))
    secret_key = hmac.new(b"WebAppData", settings.bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed_hash, provided_hash):
        raise AuthError("invalid hash")

    user_raw = flat.get("user")
    if not user_raw:
        raise AuthError("missing user data")
    user: dict[str, Any] = json.loads(user_raw)
    return user


def verify_api_key(api_key: str) -> bool:
    """Verify the static API key (fallback for local tooling)."""
    if not settings.api_key:
        return False
    return hmac.compare_digest(api_key, settings.api_key)
