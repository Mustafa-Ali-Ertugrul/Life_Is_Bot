"""Habits CRUD API tests."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Habit, User

HABIT_PAYLOAD = {"name": "Su iç", "target_hour": 9, "target_minute": 30}


async def test_list_habits_empty(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await api_client.get("/api/habits", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}


async def test_create_habit(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await api_client.post("/api/habits", headers=auth_headers, json=HABIT_PAYLOAD)
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Su iç"
    assert body["target_hour"] == 9
    assert body["target_minute"] == 30
    assert body["days_of_week"] == "1,2,3,4,5,6,7"
    assert body["is_active"] is True
    assert body["id"] > 0


async def test_create_habit_validation(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.post(
        "/api/habits", headers=auth_headers, json={**HABIT_PAYLOAD, "target_hour": 24}
    )
    assert response.status_code == 422


async def test_create_habit_invalid_days(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await api_client.post(
        "/api/habits",
        headers=auth_headers,
        json={**HABIT_PAYLOAD, "days_of_week": "8"},
    )
    assert response.status_code == 422


async def test_get_habit_owned(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    created = await api_client.post("/api/habits", headers=auth_headers, json=HABIT_PAYLOAD)
    habit_id = created.json()["id"]
    response = await api_client.get(f"/api/habits/{habit_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Su iç"


async def test_get_habit_not_owned(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    other_user = User(name="other", consent_given=True, is_active=True)
    db_session.add(other_user)
    await db_session.flush()
    db_session.add(
        Habit(
            user_id=other_user.id,
            name="Başkasının alışkanlığı",
            target_hour=8,
            target_minute=0,
            days_of_week="1,2,3,4,5,6,7",
            is_active=True,
        )
    )
    await db_session.flush()
    other_habit_id = (
        await db_session.execute(Habit.__table__.select().where(Habit.user_id == other_user.id))
    ).scalar_one()
    response = await api_client.get(f"/api/habits/{other_habit_id}", headers=auth_headers)
    assert response.status_code == 404


async def test_get_habit_missing(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await api_client.get("/api/habits/99999", headers=auth_headers)
    assert response.status_code == 404


async def test_patch_habit(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    created = await api_client.post("/api/habits", headers=auth_headers, json=HABIT_PAYLOAD)
    habit_id = created.json()["id"]
    response = await api_client.patch(
        f"/api/habits/{habit_id}",
        headers=auth_headers,
        json={"name": "Bol su iç", "is_active": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Bol su iç"
    assert body["is_active"] is False
    assert body["target_hour"] == 9


async def test_delete_habit_soft(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    created = await api_client.post("/api/habits", headers=auth_headers, json=HABIT_PAYLOAD)
    habit_id = created.json()["id"]
    response = await api_client.delete(f"/api/habits/{habit_id}", headers=auth_headers)
    assert response.status_code == 204
    fetched = await api_client.get(f"/api/habits/{habit_id}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["is_active"] is False


async def test_habits_require_auth(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/habits")
    assert response.status_code == 401
