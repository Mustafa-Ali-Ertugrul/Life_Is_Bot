"""Supplement plan CRUD API tests."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SupplementPlan, User

SUPPLEMENT_PAYLOAD = {
    "name": "D vitamini",
    "target_hour": 9,
    "target_minute": 0,
    "dose": "1x1",
    "with_food": "full",
}


async def test_list_supplement_plans_paginated(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.get("/api/supplement", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}


async def test_create_supplement_plan(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.post(
        "/api/supplement", headers=auth_headers, json=SUPPLEMENT_PAYLOAD
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "D vitamini"
    assert body["dose"] == "1x1"
    assert body["with_food"] == "full"
    assert body["days_of_week"] == "1,2,3,4,5,6,7"
    assert body["is_active"] is True
    assert body["id"] > 0


async def test_create_supplement_plan_validation(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.post(
        "/api/supplement",
        headers=auth_headers,
        json={**SUPPLEMENT_PAYLOAD, "with_food": "after"},
    )
    assert response.status_code == 422


async def test_create_supplement_plan_date_range(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.post(
        "/api/supplement",
        headers=auth_headers,
        json={
            **SUPPLEMENT_PAYLOAD,
            "start_date": "2026-08-10",
            "end_date": "2026-08-01",
        },
    )
    assert response.status_code == 422


async def test_get_supplement_plan_owned(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await api_client.post(
        "/api/supplement", headers=auth_headers, json=SUPPLEMENT_PAYLOAD
    )
    plan_id = created.json()["id"]
    response = await api_client.get(f"/api/supplement/{plan_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["name"] == "D vitamini"
    assert response.json()["dose"] == "1x1"


async def test_get_supplement_plan_not_owned(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    other_user = User(name="other", consent_given=True, is_active=True)
    db_session.add(other_user)
    await db_session.flush()
    db_session.add(
        SupplementPlan(
            user_id=other_user.id,
            name="Başkasının takviyesi",
            target_hour=20,
            target_minute=0,
            dose="1x1",
            with_food="full",
            is_active=True,
        )
    )
    await db_session.flush()
    other_plan_id = (
        await db_session.execute(
            SupplementPlan.__table__.select().where(SupplementPlan.user_id == other_user.id)
        )
    ).scalar_one()
    response = await api_client.get(f"/api/supplement/{other_plan_id}", headers=auth_headers)
    assert response.status_code == 404


async def test_patch_supplement_plan(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    created = await api_client.post(
        "/api/supplement", headers=auth_headers, json=SUPPLEMENT_PAYLOAD
    )
    plan_id = created.json()["id"]
    response = await api_client.patch(
        f"/api/supplement/{plan_id}",
        headers=auth_headers,
        json={"dose": "2x1", "is_active": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["dose"] == "2x1"
    assert body["is_active"] is False
    assert body["name"] == "D vitamini"


async def test_delete_supplement_plan_soft(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await api_client.post(
        "/api/supplement", headers=auth_headers, json=SUPPLEMENT_PAYLOAD
    )
    plan_id = created.json()["id"]
    response = await api_client.delete(f"/api/supplement/{plan_id}", headers=auth_headers)
    assert response.status_code == 204
    fetched = await api_client.get(f"/api/supplement/{plan_id}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["is_active"] is False


async def test_delete_supplement_plan_removes_from_list(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await api_client.post(
        "/api/supplement", headers=auth_headers, json=SUPPLEMENT_PAYLOAD
    )
    plan_id = created.json()["id"]
    await api_client.delete(f"/api/supplement/{plan_id}", headers=auth_headers)
    response = await api_client.get("/api/supplement", headers=auth_headers)
    assert response.status_code == 200
    assert all(item["id"] != plan_id for item in response.json()["items"])


async def test_supplement_plans_require_auth(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/supplement")
    assert response.status_code == 401
