"""Step tracker settings and logs API tests."""

from httpx import AsyncClient

SETTINGS_URL = "/api/step/settings"
LOGS_URL = "/api/step/logs"


async def test_get_settings_defaults(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await api_client.get(SETTINGS_URL, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["daily_target"] == 8000
    assert body["reminder_hour"] == 21
    assert body["reminder_minute"] == 0
    assert body["days_of_week"] == "1,2,3,4,5,6,7"
    assert body["is_active"] is True


async def test_patch_settings(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await api_client.patch(
        SETTINGS_URL,
        headers=auth_headers,
        json={"daily_target": 12000, "is_active": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["daily_target"] == 12000
    assert body["is_active"] is False
    assert body["reminder_hour"] == 21


async def test_patch_settings_invalid_goal(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.patch(
        SETTINGS_URL, headers=auth_headers, json={"daily_target": 200000}
    )
    assert response.status_code == 422


async def test_create_step_log(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await api_client.post(
        LOGS_URL, headers=auth_headers, json={"steps": 8500, "log_date": "2026-08-01"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["steps"] == 8500
    assert body["log_date"] == "2026-08-01"
    assert body["source"] == "manual"
    assert body["id"] > 0


async def test_create_step_log_upsert_same_day(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    first = await api_client.post(
        LOGS_URL, headers=auth_headers, json={"steps": 1000, "log_date": "2026-08-05"}
    )
    assert first.status_code == 201
    log_id = first.json()["id"]
    second = await api_client.post(
        LOGS_URL, headers=auth_headers, json={"steps": 9000, "log_date": "2026-08-05"}
    )
    assert second.status_code == 201
    assert second.json()["id"] == log_id
    assert second.json()["steps"] == 9000


async def test_list_step_logs_range(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    empty = await api_client.get(
        f"{LOGS_URL}?start=2026-08-01&end=2026-08-31", headers=auth_headers
    )
    assert empty.status_code == 200
    assert empty.json() == []

    for day, steps in ((1, 5001), (2, 5002)):
        response = await api_client.post(
            LOGS_URL,
            headers=auth_headers,
            json={"steps": steps, "log_date": f"2026-08-0{day}"},
        )
        assert response.status_code == 201

    response = await api_client.get(
        f"{LOGS_URL}?start=2026-08-01&end=2026-08-31", headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert [item["steps"] for item in body] == [5001, 5002]
    assert all(item["source"] == "manual" for item in body)


async def test_list_step_logs_start_after_end(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.get(
        f"{LOGS_URL}?start=2026-08-31&end=2026-08-01", headers=auth_headers
    )
    assert response.status_code == 422


async def test_get_step_log_by_date(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    await api_client.post(
        LOGS_URL, headers=auth_headers, json={"steps": 6400, "log_date": "2026-08-10"}
    )
    response = await api_client.get(f"{LOGS_URL}/2026-08-10", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["steps"] == 6400
    assert body["log_date"] == "2026-08-10"


async def test_get_step_log_missing(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await api_client.get(f"{LOGS_URL}/2026-08-10", headers=auth_headers)
    assert response.status_code == 404


async def test_step_require_auth(api_client: AsyncClient) -> None:
    response = await api_client.get(SETTINGS_URL)
    assert response.status_code == 401
