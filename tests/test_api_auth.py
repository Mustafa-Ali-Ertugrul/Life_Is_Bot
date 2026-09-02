"""API authentication tests."""

import hashlib
import hmac
import json
import time
import urllib.parse

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import create_access_token
from app.models import User
from tests.conftest import TEST_API_KEY, TEST_JWT_SECRET, TEST_TELEGRAM_USER_ID

BAD_TOKEN = "not-a-jwt"
TEST_BOT_TOKEN = "test-bot-token-12345"


def _build_telegram_init_data(
    bot_token: str,
    user: dict[str, object] | None,
    auth_date: int,
    query_id: str = "test_query",
) -> str:
    data: dict[str, str] = {"query_id": query_id, "auth_date": str(auth_date)}
    if user is not None:
        data["user"] = json.dumps(user, separators=(",", ":"))
    check_parts = [f"{k}={v}" for k, v in sorted(data.items())]
    data_check_string = "\n".join(check_parts)
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    hash_val = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    data["hash"] = hash_val
    return urllib.parse.urlencode(data)


async def test_valid_jwt_authenticates(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.get("/api/habits", headers=auth_headers)
    assert response.status_code == 200


async def test_invalid_token_rejected(
    api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch, api_user: User
) -> None:
    monkeypatch.setattr("app.api.auth.settings.jwt_secret", TEST_JWT_SECRET)
    response = await api_client.get("/api/habits", headers={"Authorization": f"Bearer {BAD_TOKEN}"})
    assert response.status_code == 401


async def test_expired_token_rejected(
    api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch, api_user: User
) -> None:
    monkeypatch.setattr("app.api.auth.settings.jwt_secret", TEST_JWT_SECRET)
    token = create_access_token(api_user.id, expires_days=-1)
    response = await api_client.get("/api/habits", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


async def test_unregistered_user_rejected(
    api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch, api_user: User
) -> None:
    monkeypatch.setattr("app.api.auth.settings.jwt_secret", TEST_JWT_SECRET)
    token = create_access_token(999_999)
    response = await api_client.get("/api/habits", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


async def test_inactive_user_rejected(
    api_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
) -> None:
    from app.models import User as UserModel

    session: AsyncSession = db_session
    user = UserModel(name="inactive", consent_given=True, is_active=False)
    session.add(user)
    await session.flush()
    monkeypatch.setattr("app.api.auth.settings.jwt_secret", TEST_JWT_SECRET)
    token = create_access_token(user.id)
    response = await api_client.get("/api/habits", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


async def test_provisioning_token_issued(
    api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch, api_user: User
) -> None:
    monkeypatch.setattr("app.api.auth.settings.provisioning_key", TEST_API_KEY)
    monkeypatch.setattr("app.api.auth.settings.jwt_secret", TEST_JWT_SECRET)
    response = await api_client.post(
        "/api/auth/token", headers={"X-Provisioning-Key": TEST_API_KEY}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    assert body["access_token"]

    habits = await api_client.get(
        "/api/habits", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert habits.status_code == 200


async def test_invalid_provisioning_key_rejected(api_client: AsyncClient) -> None:
    response = await api_client.post("/api/auth/token", headers={"X-Provisioning-Key": "wrong-key"})
    assert response.status_code == 401


async def test_missing_auth_rejected(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/habits")
    assert response.status_code == 401


async def test_api_key_header_not_leaked(api_client: AsyncClient) -> None:
    response = await api_client.get(
        "/api/habits", headers={"Authorization": f"Bearer {TEST_API_KEY}"}
    )
    assert response.status_code == 401


async def test_telegram_auth_valid_returns_jwt(
    api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.api.auth.settings.bot_token", TEST_BOT_TOKEN)
    monkeypatch.setattr("app.api.auth.settings.jwt_secret", TEST_JWT_SECRET)
    monkeypatch.setattr("app.core.config.settings.bot_token", TEST_BOT_TOKEN)
    monkeypatch.setattr("app.core.config.settings.jwt_secret", TEST_JWT_SECRET)
    user = {"id": 999888777, "first_name": "Test", "username": "testuser"}
    auth_date = int(time.time())
    init_data = _build_telegram_init_data(TEST_BOT_TOKEN, user, auth_date)
    response = await api_client.post("/api/auth/telegram", json={"initData": init_data})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    habits = await api_client.get(
        "/api/habits", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert habits.status_code == 200


async def test_telegram_auth_via_header(
    api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.api.auth.settings.bot_token", TEST_BOT_TOKEN)
    monkeypatch.setattr("app.api.auth.settings.jwt_secret", TEST_JWT_SECRET)
    monkeypatch.setattr("app.core.config.settings.bot_token", TEST_BOT_TOKEN)
    monkeypatch.setattr("app.core.config.settings.jwt_secret", TEST_JWT_SECRET)
    user = {"id": 111222333, "first_name": "Header", "username": "headeruser"}
    auth_date = int(time.time())
    init_data = _build_telegram_init_data(TEST_BOT_TOKEN, user, auth_date)
    response = await api_client.post(
        "/api/auth/telegram", headers={"X-Telegram-Init-Data": init_data}
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


async def test_telegram_auth_invalid_hash_rejected(
    api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.api.auth.settings.bot_token", TEST_BOT_TOKEN)
    monkeypatch.setattr("app.core.config.settings.bot_token", TEST_BOT_TOKEN)
    user = {"id": 123, "first_name": "Bad"}
    auth_date = int(time.time())
    init_data = _build_telegram_init_data(TEST_BOT_TOKEN, user, auth_date)
    tampered = init_data.replace("hash=", "hash=bad")
    response = await api_client.post("/api/auth/telegram", json={"initData": tampered})
    assert response.status_code == 401


async def test_telegram_auth_expired_rejected(
    api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.api.auth.settings.bot_token", TEST_BOT_TOKEN)
    monkeypatch.setattr("app.core.config.settings.bot_token", TEST_BOT_TOKEN)
    user = {"id": 123, "first_name": "Old"}
    expired_date = int(time.time()) - 90000
    init_data = _build_telegram_init_data(TEST_BOT_TOKEN, user, expired_date)
    response = await api_client.post("/api/auth/telegram", json={"initData": init_data})
    assert response.status_code == 401


async def test_telegram_auth_future_auth_date_rejected(
    api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.api.auth.settings.bot_token", TEST_BOT_TOKEN)
    monkeypatch.setattr("app.core.config.settings.bot_token", TEST_BOT_TOKEN)
    user = {"id": 123, "first_name": "Future"}
    future_date = int(time.time()) + 1000
    init_data = _build_telegram_init_data(TEST_BOT_TOKEN, user, future_date)
    response = await api_client.post("/api/auth/telegram", json={"initData": init_data})
    assert response.status_code == 401


async def test_telegram_auth_missing_auth_date_rejected(
    api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.api.auth.settings.bot_token", TEST_BOT_TOKEN)
    monkeypatch.setattr("app.core.config.settings.bot_token", TEST_BOT_TOKEN)
    data: dict[str, str] = {
        "query_id": "test",
        "user": json.dumps({"id": 123, "first_name": "NoDate"}),
    }
    check_parts = [f"{k}={v}" for k, v in sorted(data.items())]
    data_check_string = "\n".join(check_parts)
    secret_key = hmac.new(b"WebAppData", TEST_BOT_TOKEN.encode(), hashlib.sha256).digest()
    hash_val = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    data["hash"] = hash_val
    init_data = urllib.parse.urlencode(data)
    response = await api_client.post("/api/auth/telegram", json={"initData": init_data})
    assert response.status_code == 401


async def test_provisioning_with_telegram_user_id(
    api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch, api_user: User
) -> None:
    monkeypatch.setattr("app.api.auth.settings.provisioning_key", TEST_API_KEY)
    monkeypatch.setattr("app.api.auth.settings.jwt_secret", TEST_JWT_SECRET)
    tg_id = str(TEST_TELEGRAM_USER_ID)
    response = await api_client.post(
        "/api/auth/token",
        headers={"X-Provisioning-Key": TEST_API_KEY, "X-Telegram-User-Id": tg_id},
    )
    assert response.status_code == 200
    body = response.json()
    habits = await api_client.get(
        "/api/habits", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert habits.status_code == 200
