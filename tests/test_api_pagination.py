"""Pagination API tests."""

from httpx import AsyncClient

PAGINATION_PAYLOAD = {"name": "Su iç", "target_hour": 9, "target_minute": 0}


async def _create_habits(api_client: AsyncClient, headers: dict[str, str], count: int = 3) -> None:
    for index in range(count):
        await api_client.post(
            "/api/habits",
            headers=headers,
            json={**PAGINATION_PAYLOAD, "name": f"Alışkanlık {index}"},
        )


async def test_list_first_page(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    await _create_habits(api_client, auth_headers)
    response = await api_client.get("/api/habits?limit=2&offset=0", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["total"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 0


async def test_list_second_page(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    await _create_habits(api_client, auth_headers)
    response = await api_client.get("/api/habits?limit=2&offset=2", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["total"] == 3
    assert body["items"][0]["name"] == "Alışkanlık 2"


async def test_list_offset_beyond_total(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    await _create_habits(api_client, auth_headers)
    response = await api_client.get("/api/habits?offset=100", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 3


async def test_list_invalid_limit_low(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.get("/api/habits?limit=0", headers=auth_headers)
    assert response.status_code == 422


async def test_list_invalid_limit_high(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.get("/api/habits?limit=200", headers=auth_headers)
    assert response.status_code == 422
