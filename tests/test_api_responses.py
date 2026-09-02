"""Mobile notification response API tests."""

from httpx import AsyncClient

MED_PAYLOAD = {"name": "Test ilacı", "target_hour": 9, "target_minute": 0}
HABIT_PAYLOAD = {"name": "Su iç", "target_hour": 9, "target_minute": 30}


async def _create_medication(api_client: AsyncClient, auth_headers: dict[str, str]) -> int:
    response = await api_client.post("/api/medications", headers=auth_headers, json=MED_PAYLOAD)
    assert response.status_code == 201
    return int(response.json()["id"])


async def _create_habit(api_client: AsyncClient, auth_headers: dict[str, str]) -> int:
    response = await api_client.post("/api/habits", headers=auth_headers, json=HABIT_PAYLOAD)
    assert response.status_code == 201
    return int(response.json()["id"])


async def test_submit_taken_response(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    med_id = await _create_medication(api_client, auth_headers)
    response = await api_client.post(
        "/api/responses",
        headers=auth_headers,
        json={
            "related_type": "medication_plan",
            "related_id": med_id,
            "response": "taken",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "positive"
    assert body["response"] == "taken"
    assert body["source"] == "mobile_app"


async def test_submit_overwrites_previous_response(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    med_id = await _create_medication(api_client, auth_headers)
    payload = {"related_type": "medication_plan", "related_id": med_id}
    first = await api_client.post(
        "/api/responses", headers=auth_headers, json={**payload, "response": "taken"}
    )
    assert first.status_code == 201
    second = await api_client.post(
        "/api/responses", headers=auth_headers, json={**payload, "response": "not_taken"}
    )
    assert second.status_code == 201
    assert second.json()["status"] == "negative"
    assert second.json()["event_id"] == first.json()["event_id"]


async def test_submit_habit_done_response(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    habit_id = await _create_habit(api_client, auth_headers)
    response = await api_client.post(
        "/api/responses",
        headers=auth_headers,
        json={"related_type": "habit", "related_id": habit_id, "response": "done"},
    )
    assert response.status_code == 201
    assert response.json()["status"] == "positive"


async def test_submit_rejects_unsupported_response_type(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    med_id = await _create_medication(api_client, auth_headers)
    response = await api_client.post(
        "/api/responses",
        headers=auth_headers,
        json={"related_type": "medication_plan", "related_id": med_id, "response": "yes"},
    )
    assert response.status_code == 422


async def test_submit_unknown_related_type(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.post(
        "/api/responses",
        headers=auth_headers,
        json={"related_type": "unknown_type", "related_id": 1, "response": "done"},
    )
    assert response.status_code == 404
