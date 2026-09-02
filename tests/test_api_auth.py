"""API authentication tests."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import create_access_token
from app.models import User
from tests.conftest import TEST_API_KEY, TEST_JWT_SECRET

BAD_TOKEN = "not-a-jwt"


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
