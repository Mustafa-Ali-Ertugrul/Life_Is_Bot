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


async def test_month_days_filters_by_bot_key(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    api_user: User,
    db_session: AsyncSession,
) -> None:
    current = now_in(api_user.timezone)
    day1 = date(current.year, current.month, 1)
    day3 = date(current.year, current.month, 3)
    day5 = date(current.year, current.month, 5)
    await _add_event(
        db_session,
        api_user.id,
        ReminderStatus.POSITIVE.value,
        day1,
        bot_key=BotKey.SPORT.value,
        related_type="s",
        label="sport-done",
    )
    await _add_event(
        db_session,
        api_user.id,
        ReminderStatus.NEGATIVE.value,
        day3,
        bot_key=BotKey.SPORT.value,
        related_type="s",
        label="sport-missed",
    )
    await _add_event(
        db_session,
        api_user.id,
        ReminderStatus.POSITIVE.value,
        day5,
        bot_key=BotKey.HABIT.value,
        related_type="h",
        label="habit-done",
    )
    response = await api_client.get(
        f"/api/reports/monthly/days?bot_key={BotKey.SPORT.value}"
        f"&year={current.year}&month={current.month}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["bot_key"] == BotKey.SPORT.value
    assert body["scheduled_days"] == [day1.isoformat(), day3.isoformat()]
    assert body["completed_days"] == [day1.isoformat()]


async def test_month_days_all_bots(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    api_user: User,
    db_session: AsyncSession,
) -> None:
    current = now_in(api_user.timezone)
    day1 = date(current.year, current.month, 1)
    day5 = date(current.year, current.month, 5)
    await _add_event(
        db_session,
        api_user.id,
        ReminderStatus.POSITIVE.value,
        day1,
        bot_key=BotKey.SPORT.value,
        related_type="s",
        label="sport",
    )
    await _add_event(
        db_session,
        api_user.id,
        ReminderStatus.POSITIVE.value,
        day5,
        bot_key=BotKey.HABIT.value,
        related_type="h",
        label="habit",
    )
    response = await api_client.get(
        f"/api/reports/monthly/days?year={current.year}&month={current.month}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["bot_key"] is None
    assert body["scheduled_days"] == [day1.isoformat(), day5.isoformat()]
    assert body["completed_days"] == [day1.isoformat(), day5.isoformat()]


async def test_month_days_requires_auth(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/reports/monthly/days?year=2026&month=1")
    assert response.status_code == 401


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


async def test_yearly_default_empty(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    api_user: User,
) -> None:
    response = await api_client.get(
        f"/api/reports/yearly?year={now_in(api_user.timezone).year}", headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == api_user.id
    assert body["total"] == 0
    assert body["total_completed"] == 0
    assert body["completion_rate"] == 0.0
    assert body["best_month"] is None
    assert body["worst_month"] is None
    assert len(body["monthly"]) == 12
    assert all(item["total"] == 0 for item in body["monthly"])


async def test_yearly_default_current_year(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    api_user: User,
) -> None:
    response = await api_client.get("/api/reports/yearly", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["year"] == now_in(api_user.timezone).year


async def test_yearly_invalid_year(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await api_client.get("/api/reports/yearly?year=1999", headers=auth_headers)
    assert response.status_code == 422

    response = await api_client.get("/api/reports/yearly?year=2101", headers=auth_headers)
    assert response.status_code == 422


async def test_yearly_aggregates_months(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    api_user: User,
    db_session: AsyncSession,
) -> None:
    current = now_in(api_user.timezone)
    await _add_event(
        db_session,
        api_user.id,
        ReminderStatus.POSITIVE.value,
        date(current.year, 1, 10),
        related_type="a",
        label="1",
    )
    await _add_event(
        db_session,
        api_user.id,
        ReminderStatus.NEGATIVE.value,
        date(current.year, 8, 15),
        related_type="b",
        label="2",
    )
    await _add_event(
        db_session,
        api_user.id,
        ReminderStatus.POSITIVE.value,
        date(current.year, 8, 16),
        related_type="c",
        label="3",
    )
    response = await api_client.get(
        f"/api/reports/yearly?year={current.year}", headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["total_completed"] == 2
    assert body["total_missed"] == 1
    assert body["completion_rate"] == round(2 * 100 / 3, 1)
    monthly = {item["month"]: item for item in body["monthly"]}
    assert monthly[1]["total"] == 1
    assert monthly[8]["total"] == 2
    assert monthly[1]["completed"] == 1
    assert body["best_month"] is not None
    assert body["best_month"]["month"] == 1
    assert body["worst_month"] is not None
    assert body["worst_month"]["month"] == 8


async def test_yearly_requires_auth(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/reports/yearly")
    assert response.status_code == 401


async def test_yearly_rate_limited(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await api_client.get("/api/reports/yearly", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["x-ratelimit-limit"] == "30"


async def test_streak_requires_auth(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/reports/streak")
    assert response.status_code == 401


async def test_streak_default_empty(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    api_user: User,
) -> None:
    response = await api_client.get("/api/reports/streak", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == api_user.id
    assert body["current"] == 0
    assert body["longest"] == 0
    assert body["today_completed"] is False


async def test_streak_counts_consecutive_days(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    api_user: User,
    db_session: AsyncSession,
) -> None:
    today = now_in(api_user.timezone).date()
    await _add_event(
        db_session, api_user.id, ReminderStatus.POSITIVE.value, today, related_type="a", label="1"
    )
    await _add_event(
        db_session,
        api_user.id,
        ReminderStatus.POSITIVE.value,
        today - timedelta(days=1),
        related_type="b",
        label="2",
    )
    await _add_event(
        db_session,
        api_user.id,
        ReminderStatus.NEGATIVE.value,
        today - timedelta(days=2),
        related_type="c",
        label="3",
    )
    response = await api_client.get("/api/reports/streak", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["current"] == 2
    assert body["longest"] == 2
    assert body["today_completed"] is True


async def test_streak_rate_limited(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await api_client.get("/api/reports/streak", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["x-ratelimit-limit"] == "30"
