"""Rate limiting behaviour tests for the API."""

import pytest
from httpx import AsyncClient

from app.api.rate_limit import limiter

CRUD_LIMIT = 60
REPORTS_LIMIT = 30


@pytest.mark.asyncio
async def test_health_not_rate_limited(api_client: AsyncClient) -> None:
    """Health endpoint is exempt from rate limiting."""
    for _ in range(70):
        response = await api_client.get("/health")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_crud_response_has_rate_limit_headers(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """CRUD responses expose X-RateLimit headers."""
    response = await api_client.get("/api/habits", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["x-ratelimit-limit"] == str(CRUD_LIMIT)
    assert response.headers["x-ratelimit-remaining"] == str(CRUD_LIMIT - 1)
    assert "x-ratelimit-reset" in response.headers


@pytest.mark.asyncio
async def test_crud_rate_limit_exceeded(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """The 61st CRUD request within a minute returns 429."""
    for i in range(CRUD_LIMIT):
        response = await api_client.get("/api/habits", headers=auth_headers)
        assert response.status_code == 200, f"request {i + 1} failed"

    response = await api_client.get("/api/habits", headers=auth_headers)
    assert response.status_code == 429
    data = response.json()
    assert data["detail"] == "Rate limit exceeded"
    assert isinstance(data["retry_after"], int)
    assert data["retry_after"] >= 1


@pytest.mark.asyncio
async def test_429_response_has_rate_limit_headers(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """The 429 response also carries X-RateLimit headers."""
    for _ in range(CRUD_LIMIT):
        await api_client.get("/api/habits", headers=auth_headers)
    response = await api_client.get("/api/habits", headers=auth_headers)
    assert response.status_code == 429
    assert response.headers["x-ratelimit-limit"] == str(CRUD_LIMIT)
    assert response.headers["x-ratelimit-remaining"] == "0"


@pytest.mark.asyncio
async def test_reports_have_lower_limit(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Report endpoints use the lower per-minute limit."""
    response = await api_client.get("/api/reports/daily", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["x-ratelimit-limit"] == str(REPORTS_LIMIT)


@pytest.mark.asyncio
async def test_reports_rate_limit_exceeded(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """The 31st report request within a minute returns 429."""
    for i in range(REPORTS_LIMIT):
        response = await api_client.get("/api/reports/daily", headers=auth_headers)
        assert response.status_code == 200, f"request {i + 1} failed"

    response = await api_client.get("/api/reports/daily", headers=auth_headers)
    assert response.status_code == 429


@pytest.mark.asyncio
async def test_per_user_limits_are_separate(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    auth_headers_user2: dict[str, str],
) -> None:
    """Different users have independent rate limit counters."""
    for _ in range(CRUD_LIMIT):
        await api_client.get("/api/habits", headers=auth_headers)

    response = await api_client.get("/api/habits", headers=auth_headers)
    assert response.status_code == 429

    response = await api_client.get("/api/habits", headers=auth_headers_user2)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_endpoint_scopes_are_separate(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Exhausting one endpoint does not exhaust another."""
    for _ in range(CRUD_LIMIT):
        await api_client.get("/api/habits", headers=auth_headers)

    response = await api_client.get("/api/medications", headers=auth_headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_rate_limit_can_be_disabled(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """With the limiter disabled, exhausted counters do not block requests."""
    for _ in range(CRUD_LIMIT):
        await api_client.get("/api/habits", headers=auth_headers)
    response = await api_client.get("/api/habits", headers=auth_headers)
    assert response.status_code == 429

    limiter.enabled = False
    try:
        response = await api_client.get("/api/habits", headers=auth_headers)
        assert response.status_code == 200
    finally:
        limiter.enabled = True


@pytest.mark.asyncio
async def test_webhook_not_rate_limited(api_client: AsyncClient) -> None:
    """The Telegram webhook endpoint is exempt from rate limiting."""
    for _ in range(20):
        response = await api_client.post(
            "/api/webhook/telegram",
            json={"update_id": 1, "message": {}},
            headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
        )
        assert response.status_code != 429


@pytest.mark.asyncio
async def test_unauthenticated_request_is_rejected(api_client: AsyncClient) -> None:
    """Requests without credentials fail with 401 before rate limiting."""
    response = await api_client.get("/api/habits")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_authenticated_requests_are_rate_limited(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """JWT-authenticated requests consume the per-user counter."""
    response = await api_client.get("/api/habits", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["x-ratelimit-limit"] == str(CRUD_LIMIT)
