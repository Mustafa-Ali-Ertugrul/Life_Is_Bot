"""Sport plan CRUD API tests."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SportPlan, User

SPORT_PAYLOAD = {"sport_type": "Koşu", "target_hour": 7, "target_minute": 30}


async def test_list_sport_plans_paginated(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.get("/api/sport", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}


async def test_create_sport_plan(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await api_client.post("/api/sport", headers=auth_headers, json=SPORT_PAYLOAD)
    assert response.status_code == 201
    body = response.json()
    assert body["sport_type"] == "Koşu"
    assert body["target_hour"] == 7
    assert body["target_minute"] == 30
    assert body["days_of_week"] == "1,2,3,4,5,6,7"
    assert body["is_active"] is True
    assert body["id"] > 0


async def test_create_sport_plan_validation(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.post(
        "/api/sport", headers=auth_headers, json={**SPORT_PAYLOAD, "target_hour": 24}
    )
    assert response.status_code == 422


async def test_get_sport_plan_owned(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    created = await api_client.post("/api/sport", headers=auth_headers, json=SPORT_PAYLOAD)
    plan_id = created.json()["id"]
    response = await api_client.get(f"/api/sport/{plan_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["sport_type"] == "Koşu"


async def test_get_sport_plan_not_owned(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    other_user = User(name="other", consent_given=True, is_active=True)
    db_session.add(other_user)
    await db_session.flush()
    db_session.add(
        SportPlan(
            user_id=other_user.id,
            sport_type="Yüzme",
            target_hour=8,
            target_minute=0,
            days_of_week="1,2,3,4,5",
            is_active=True,
        )
    )
    await db_session.flush()
    other_plan_id = (
        await db_session.execute(
            SportPlan.__table__.select().where(SportPlan.user_id == other_user.id)
        )
    ).scalar_one()
    response = await api_client.get(f"/api/sport/{other_plan_id}", headers=auth_headers)
    assert response.status_code == 404


async def test_patch_sport_plan(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    created = await api_client.post("/api/sport", headers=auth_headers, json=SPORT_PAYLOAD)
    plan_id = created.json()["id"]
    response = await api_client.patch(
        f"/api/sport/{plan_id}",
        headers=auth_headers,
        json={"sport_type": "Bisiklet", "is_active": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["sport_type"] == "Bisiklet"
    assert body["is_active"] is False
    assert body["target_hour"] == 7


async def test_delete_sport_plan_soft(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await api_client.post("/api/sport", headers=auth_headers, json=SPORT_PAYLOAD)
    plan_id = created.json()["id"]
    response = await api_client.delete(f"/api/sport/{plan_id}", headers=auth_headers)
    assert response.status_code == 204
    fetched = await api_client.get(f"/api/sport/{plan_id}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["is_active"] is False


async def test_delete_sport_plan_removes_from_list(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await api_client.post("/api/sport", headers=auth_headers, json=SPORT_PAYLOAD)
    plan_id = created.json()["id"]
    await api_client.delete(f"/api/sport/{plan_id}", headers=auth_headers)
    response = await api_client.get("/api/sport", headers=auth_headers)
    assert response.status_code == 200
    assert all(item["id"] != plan_id for item in response.json()["items"])


async def test_sport_plans_require_auth(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/sport")
    assert response.status_code == 401
