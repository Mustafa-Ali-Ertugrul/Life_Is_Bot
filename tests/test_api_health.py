"""API health endpoint tests."""

import pytest
from httpx import AsyncClient

from app.api import API_VERSION
from app.api.deps import get_settings


async def test_health_returns_ok(api_client: AsyncClient) -> None:
    response = await api_client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] is True
    assert body["version"] == API_VERSION


async def test_health_uses_overridden_db_session(
    api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _boom() -> None:
        raise AssertionError("unit_of_work must not be called from tests")

    monkeypatch.setattr("app.api.deps.unit_of_work", _boom)

    response = await api_client.get("/health")

    assert response.status_code == 200
    assert response.json()["database"] is True


async def test_health_cors_preflight_allows_origin(api_client: AsyncClient) -> None:
    response = await api_client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"


async def test_openapi_includes_health(api_client: AsyncClient) -> None:
    response = await api_client.get("/openapi.json")

    assert response.status_code == 200
    assert "/health" in response.json()["paths"]


async def test_get_settings_returns_defaults() -> None:
    settings = get_settings()

    assert settings.api_host == "127.0.0.1"
    assert settings.api_port == 8000
    assert settings.api_cors_origins == ["*"]
