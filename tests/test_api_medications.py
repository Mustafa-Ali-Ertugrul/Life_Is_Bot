"""Medications CRUD API tests."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MedicationPlan, User

MEDICATION_PAYLOAD = {
    "name": "C vitamini",
    "target_hour": 8,
    "target_minute": 15,
    "dose": "1x1",
    "with_food": "full",
}


async def test_list_medications_empty(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.get("/api/medications", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}


async def test_create_medication(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await api_client.post(
        "/api/medications", headers=auth_headers, json=MEDICATION_PAYLOAD
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "C vitamini"
    assert body["target_hour"] == 8
    assert body["target_minute"] == 15
    assert body["dose"] == "1x1"
    assert body["with_food"] == "full"
    assert body["notes"] is None
    assert body["is_active"] is True
    assert body["id"] > 0


async def test_create_medication_validation(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.post(
        "/api/medications",
        headers=auth_headers,
        json={**MEDICATION_PAYLOAD, "with_food": "after"},
    )
    assert response.status_code == 422


async def test_create_medication_date_range(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.post(
        "/api/medications",
        headers=auth_headers,
        json={
            **MEDICATION_PAYLOAD,
            "start_date": "2026-08-10",
            "end_date": "2026-08-01",
        },
    )
    assert response.status_code == 422


async def test_get_medication_owned(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    created = await api_client.post(
        "/api/medications", headers=auth_headers, json=MEDICATION_PAYLOAD
    )
    plan_id = created.json()["id"]
    response = await api_client.get(f"/api/medications/{plan_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["name"] == "C vitamini"
    assert response.json()["dose"] == "1x1"


async def test_get_medication_not_owned(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    other_user = User(name="other", consent_given=True, is_active=True)
    db_session.add(other_user)
    await db_session.flush()
    db_session.add(
        MedicationPlan(
            user_id=other_user.id,
            name="Başkasının ilacı",
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
            MedicationPlan.__table__.select().where(MedicationPlan.user_id == other_user.id)
        )
    ).scalar_one()
    response = await api_client.get(f"/api/medications/{other_plan_id}", headers=auth_headers)
    assert response.status_code == 404


async def test_get_medication_missing(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.get("/api/medications/99999", headers=auth_headers)
    assert response.status_code == 404


async def test_patch_medication(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    created = await api_client.post(
        "/api/medications", headers=auth_headers, json=MEDICATION_PAYLOAD
    )
    plan_id = created.json()["id"]
    response = await api_client.patch(
        f"/api/medications/{plan_id}",
        headers=auth_headers,
        json={"dose": "2x1", "is_active": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["dose"] == "2x1"
    assert body["is_active"] is False
    assert body["name"] == "C vitamini"


async def test_delete_medication_soft(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await api_client.post(
        "/api/medications", headers=auth_headers, json=MEDICATION_PAYLOAD
    )
    plan_id = created.json()["id"]
    response = await api_client.delete(f"/api/medications/{plan_id}", headers=auth_headers)
    assert response.status_code == 204
    fetched = await api_client.get(f"/api/medications/{plan_id}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["is_active"] is False


async def test_delete_medication_removes_from_list(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await api_client.post(
        "/api/medications", headers=auth_headers, json=MEDICATION_PAYLOAD
    )
    plan_id = created.json()["id"]
    await api_client.delete(f"/api/medications/{plan_id}", headers=auth_headers)
    response = await api_client.get("/api/medications", headers=auth_headers)
    assert response.status_code == 200
    assert all(item["id"] != plan_id for item in response.json()["items"])


async def test_medications_require_auth(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/medications")
    assert response.status_code == 401
