"""API authentication tests."""

import time

import pytest
from httpx import AsyncClient

from app.models import User
from tests.conftest import TEST_API_KEY, TEST_BOT_TOKEN, TEST_TELEGRAM_USER_ID, make_init_data

BAD_HASH = "0" * 64


async def test_valid_init_data_authenticates(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.get("/api/habits", headers=auth_headers)
    assert response.status_code == 200


async def test_invalid_hash_rejected(
    api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch, api_user: User
) -> None:
    monkeypatch.setattr("app.api.auth.settings.bot_token", TEST_BOT_TOKEN)
    init_data = make_init_data(TEST_TELEGRAM_USER_ID)
    init_data = init_data.rsplit("hash=", 1)[0] + f"hash={BAD_HASH}"
    response = await api_client.get("/api/habits", headers={"Authorization": f"Bearer {init_data}"})
    assert response.status_code == 401


async def test_expired_init_data_rejected(
    api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch, api_user: User
) -> None:
    monkeypatch.setattr("app.api.auth.settings.bot_token", TEST_BOT_TOKEN)
    old_auth_date = int(time.time()) - 90_000
    init_data = make_init_data(TEST_TELEGRAM_USER_ID, auth_date=old_auth_date)
    response = await api_client.get("/api/habits", headers={"Authorization": f"Bearer {init_data}"})
    assert response.status_code == 401


async def test_missing_user_rejected(
    api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch, api_user: User
) -> None:
    monkeypatch.setattr("app.api.auth.settings.bot_token", TEST_BOT_TOKEN)
    init_data = make_init_data()
    response = await api_client.get("/api/habits", headers={"Authorization": f"Bearer {init_data}"})
    assert response.status_code == 401


async def test_unregistered_user_rejected(
    api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch, api_user: User
) -> None:
    monkeypatch.setattr("app.api.auth.settings.bot_token", TEST_BOT_TOKEN)
    init_data = make_init_data(999_999)
    response = await api_client.get("/api/habits", headers={"Authorization": f"Bearer {init_data}"})
    assert response.status_code == 401


async def test_valid_api_key_authenticates(
    api_client: AsyncClient, api_key_headers: dict[str, str]
) -> None:
    response = await api_client.get("/api/habits", headers=api_key_headers)
    assert response.status_code == 200


async def test_invalid_api_key_rejected(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/habits", headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401


async def test_missing_auth_rejected(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/habits")
    assert response.status_code == 401


async def test_api_key_header_not_leaked(api_client: AsyncClient) -> None:
    response = await api_client.get(
        "/api/habits", headers={"Authorization": f"Bearer {TEST_API_KEY}"}
    )
    assert response.status_code == 401
