"""Reports API tests."""

from datetime import UTC, date, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone import now_in
from app.models import BotKey, ReminderEvent, ReminderStatus, User


async def _add_event(
    db_session: AsyncSession,
    user_id: int,
    status: str,
    local_date: date,
    *,
    bot_key: str = BotKey.HABIT.value,
    related_type: str = "test_item",
    label: str = "item",
) -> None:
    db_session.add(
        ReminderEvent(
            user_id=user_id,
            bot_key=bot_key,
            related_type=related_type,
            related_id=None,
            scheduled_at=datetime.now(UTC),
            scheduled_local_date=local_date,
            dedupe_key=f"{bot_key}:{related_type}:{label}:{local_date.isoformat()}",
            status=status,
        )
    )
    await db_session.flush()


async def test_reports_require_auth(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/reports/daily")
    assert response.status_code == 401


async def test_daily_default_empty(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await api_client.get("/api/reports/daily", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["completed"] == 0
    assert body["missed"] == 0
    assert body["unanswered"] == 0
    assert body["completed_items"] == []
    assert body["missed_items"] == []
    assert body["step_steps"] is None
    assert body["step_goal"] is None
    assert body["date"]


async def test_daily_with_date(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    api_user: User,
) -> None:
    day = now_in(api_user.timezone).date().isoformat()
    response = await api_client.get(f"/api/reports/daily?date={day}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["date"] == day


async def test_daily_invalid_date(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await api_client.get("/api/reports/daily?date=2026-13-99", headers=auth_headers)
    assert response.status_code == 422


async def test_daily_counts_events(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    api_user: User,
    db_session: AsyncSession,
) -> None:
    today = now_in(api_user.timezone).date()
    await _add_event(
        db_session,
        api_user.id,
        ReminderStatus.POSITIVE.value,
        today,
        related_type="su_ic",
        label="1",
    )
    await _add_event(
        db_session,
        api_user.id,
        ReminderStatus.NEGATIVE.value,
        today,
        related_type="yuruyus",
        label="2",
    )
    await _add_event(
        db_session,
        api_user.id,
        ReminderStatus.NO_RESPONSE.value,
        today,
        related_type="ilac",
        label="3",
    )
    response = await api_client.get(
        f"/api/reports/daily?date={today.isoformat()}", headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["completed"] == 1
    assert body["missed"] == 1
    assert body["unanswered"] == 1
    assert body["completed_items"] == ["su_ic"]
    assert body["missed_items"] == ["yuruyus"]


async def test_weekly_default_empty(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await api_client.get("/api/reports/weekly", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["completed"] == 0
    assert body["missed"] == 0
    assert body["unanswered"] == 0
    assert body["compliance_rate"] == 0
    assert body["best_day"] is None
    assert body["weakest_day"] is None
    assert body["week_start"]
    assert body["week_end"]


async def test_weekly_with_week_start(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    api_user: User,
) -> None:
    week_start = now_in(api_user.timezone).date().isoformat()
    response = await api_client.get(
        f"/api/reports/weekly?week_start={week_start}", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["week_start"] == week_start


async def test_weekly_counts_events(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    api_user: User,
    db_session: AsyncSession,
) -> None:
    today = now_in(api_user.timezone).date()
    week_start = today - timedelta(days=today.weekday())
    await _add_event(
        db_session,
        api_user.id,
        ReminderStatus.POSITIVE.value,
        week_start,
        related_type="a",
        label="1",
    )
    await _add_event(
        db_session,
        api_user.id,
        ReminderStatus.NEGATIVE.value,
        week_start,
        related_type="b",
        label="2",
    )
    await _add_event(
        db_session,
        api_user.id,
        ReminderStatus.POSITIVE.value,
        week_start,
        related_type="c",
        label="3",
    )
    response = await api_client.get(
        f"/api/reports/weekly?week_start={week_start.isoformat()}", headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["completed"] == 2
    assert body["missed"] == 1
    assert body["compliance_rate"] == 67
    assert body["best_day"] == week_start.isoweekday()
    assert body["weakest_day"] == week_start.isoweekday()


async def test_monthly_year_month(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await api_client.get("/api/reports/monthly?year=2026&month=7", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] > 0
    assert body["year"] == 2026
    assert body["month"] == 7
    assert body["bot_stats"] == []
    assert body["total"] == 0
    assert body["total_completed"] == 0
    assert body["completion_rate"] == 0.0


async def test_monthly_default_current(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    api_user: User,
) -> None:
    current = now_in(api_user.timezone)
    response = await api_client.get("/api/reports/monthly", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["year"] == current.year
    assert body["month"] == current.month


async def test_monthly_invalid_month(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await api_client.get("/api/reports/monthly?year=2026&month=13", headers=auth_headers)
    assert response.status_code == 422


async def test_monthly_counts_events(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    api_user: User,
    db_session: AsyncSession,
) -> None:
    current = now_in(api_user.timezone)
    first = date(current.year, current.month, 1)
    await _add_event(
        db_session,
        api_user.id,
        ReminderStatus.POSITIVE.value,
        first,
        bot_key=BotKey.HABIT.value,
        related_type="h",
        label="1",
    )
    await _add_event(
        db_session,
        api_user.id,
        ReminderStatus.NEGATIVE.value,
        first,
        bot_key=BotKey.SPORT.value,
        related_type="s",
        label="2",
    )
    await _add_event(
        db_session,
        api_user.id,
        ReminderStatus.SNOOZED.value,
        first,
        bot_key=BotKey.SPORT.value,
        related_type="s2",
        label="3",
    )
    response = await api_client.get(
        f"/api/reports/monthly?year={current.year}&month={current.month}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    stats = {item["bot_key"]: item for item in body["bot_stats"]}
    assert set(stats) == {BotKey.HABIT.value, BotKey.SPORT.value}
    assert stats[BotKey.HABIT.value]["completed"] == 1
    assert stats[BotKey.SPORT.value]["total"] == 2
    assert stats[BotKey.SPORT.value]["missed"] == 1
    assert stats[BotKey.SPORT.value]["snoozed"] == 1
    assert body["total"] == 3
    assert body["total_completed"] == 1
    assert body["total_missed"] == 1
    assert body["completion_rate"] == round(1 * 100 / 3, 1)


async def test_reports_scoped_to_user(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    api_user: User,
    db_session: AsyncSession,
) -> None:
    other = User(name="other", consent_given=True, is_active=True, timezone="Europe/Istanbul")
    db_session.add(other)
    await db_session.flush()
    today = now_in(api_user.timezone).date()
    await _add_event(
        db_session,
        other.id,
        ReminderStatus.POSITIVE.value,
        today,
        related_type="gizli",
        label="1",
    )
    response = await api_client.get(
        f"/api/reports/daily?date={today.isoformat()}", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["total"] == 0
