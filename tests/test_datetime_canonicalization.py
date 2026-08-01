"""Regression tests for datetime canonicalization (tracks #29).

Covers the UTC wall-clock storage contract: aware values are stored as
offset-less strings, due queries compare against UTC wall-clock, and
scheduler-style aware `now` values must not shift due evaluation.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone import get_user_timezone
from app.models import BotKey
from app.services import habit_service, reminder_service

HABIT_UTC_NAIVE = "2026-08-01 06:00:00.000000"  # 09:00 Europe/Istanbul instant


async def _user(db_session: AsyncSession, *, timezone: str = "Europe/Istanbul") -> int:
    await db_session.execute(
        text(
            "INSERT INTO users (id, timezone, language, consent_given, is_active, "
            "notifications_enabled, week_start_day, quiet_hours_enabled) VALUES "
            "(1, :tz, 'tr', 1, 1, 1, 1, 0)"
        ),
        {"tz": timezone},
    )
    await db_session.commit()
    return 1


async def _seed_pending(
    db_session: AsyncSession,
    user_id: int,
    *,
    stored_at: str,
    status: str = "scheduled",
    related_type: str = "habit",
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO reminder_events "
            "(user_id, bot_key, related_type, scheduled_at, status, interpretation_json, "
            "created_at, scheduled_local_date, dedupe_key) "
            "VALUES (:u, 'habit_bot', :rt, :at, :status, '{}', :at, '2026-08-01', "
            "'habit_bot:none:0:2026-08-01')"
        ),
        {"u": user_id, "at": stored_at, "status": status, "rt": related_type},
    )
    await db_session.commit()


async def test_aware_utc_roundtrip_is_stored_naive(db_session: AsyncSession) -> None:
    """Aware UTC scheduled_at is persisted as an offset-less string."""
    await _user(db_session)
    event = await reminder_service.create_event(
        db_session,
        user_id=1,
        bot_key=BotKey.HABIT,
        scheduled_at=datetime(2026, 8, 1, 6, 0, tzinfo=UTC),
    )
    row = (
        await db_session.execute(
            text("SELECT scheduled_at FROM reminder_events WHERE id = :id"),
            {"id": event.id},
        )
    ).scalar_one()
    assert row == HABIT_UTC_NAIVE
    assert not row.endswith(("+", "Z"))
    assert event.scheduled_at.tzinfo is None


async def test_create_event_normalizes_aware_local_to_utc(db_session: AsyncSession) -> None:
    """An aware Istanbul value is stored as its UTC wall-clock instant."""
    await _user(db_session)
    event = await reminder_service.create_event(
        db_session,
        user_id=1,
        bot_key=BotKey.HABIT,
        scheduled_at=datetime(2026, 8, 1, 9, 0, tzinfo=get_user_timezone("Europe/Istanbul")),
    )
    assert event.scheduled_at == datetime(2026, 8, 1, 6, 0)
    row = (
        await db_session.execute(
            text("SELECT scheduled_at FROM reminder_events WHERE id = :id"),
            {"id": event.id},
        )
    ).scalar_one()
    assert row == HABIT_UTC_NAIVE


async def test_find_due_events_not_early_for_scheduler_clock(db_session: AsyncSession) -> None:
    """Regression: a habit scheduled for 09:00 Istanbul (06:00 UTC) must not
    be due at 06:00 Istanbul when queried with an aware Istanbul clock."""
    await _user(db_session)
    await _seed_pending(db_session, 1, stored_at=HABIT_UTC_NAIVE)

    early = datetime(2026, 8, 1, 6, 0, tzinfo=get_user_timezone("Europe/Istanbul"))
    due_early = await reminder_service.find_due_events(db_session, early)
    assert due_early == []

    on_time = datetime(2026, 8, 1, 9, 0, tzinfo=get_user_timezone("Europe/Istanbul"))
    due_on_time = await reminder_service.find_due_events(db_session, on_time)
    assert len(due_on_time) == 1
    assert due_on_time[0].user_id == 1


async def test_find_due_events_utc_clock_matches_storage(db_session: AsyncSession) -> None:
    """Same instants passed as UTC-aware now yield the same boundary."""
    await _user(db_session)
    await _seed_pending(db_session, 1, stored_at=HABIT_UTC_NAIVE)

    before = await reminder_service.find_due_events(
        db_session, datetime(2026, 8, 1, 5, 59, tzinfo=UTC)
    )
    assert before == []

    at = await reminder_service.find_due_events(db_session, datetime(2026, 8, 1, 6, 0, tzinfo=UTC))
    assert len(at) == 1


async def test_find_due_events_ignores_terminal_rows(db_session: AsyncSession) -> None:
    """A stored UTC naive past value in a terminal status is not returned."""
    await _user(db_session)
    await _seed_pending(db_session, 1, stored_at="2026-07-31 06:00:00.000000", status="positive")

    due = await reminder_service.find_due_events(db_session, datetime(2026, 8, 1, 6, 0, tzinfo=UTC))

    assert due == []


async def test_scheduled_local_date_uses_user_timezone(db_session: AsyncSession) -> None:
    """A UTC scheduled_at renders the correct local date per user tz."""
    await _user(db_session, timezone="Asia/Tokyo")

    local_date = await reminder_service._scheduled_local_date(
        db_session,
        1,
        datetime(2026, 8, 1, 20, 0, tzinfo=UTC),  # 2026-08-02 05:00 in Tokyo
    )

    assert local_date.isoformat() == "2026-08-02"


async def test_scheduled_local_date_naive_assumes_utc(db_session: AsyncSession) -> None:
    """A naive scheduled_at is interpreted as UTC wall-clock (canonical)."""
    await _user(db_session, timezone="Asia/Tokyo")

    local_date = await reminder_service._scheduled_local_date(
        db_session,
        1,
        datetime(2026, 8, 1, 8, 0),  # naive UTC wall-clock
    )

    assert local_date.isoformat() == "2026-08-01"
    # 08:00 UTC + 9h = 17:00 Tokyo, same date; a +3h Istanbul reading would also match,
    # so use a boundary case: 18:00 UTC is 03:00 next day in Tokyo.
    next_day = await reminder_service._scheduled_local_date(
        db_session, 1, datetime(2026, 8, 1, 18, 0)
    )
    assert next_day.isoformat() == "2026-08-02"


async def test_reschedule_keeps_utc_wall_clock(db_session: AsyncSession) -> None:
    """Rescheduling with an aware Istanbul value stores the UTC instant."""
    await _user(db_session)
    event = await reminder_service.create_event(
        db_session,
        user_id=1,
        bot_key=BotKey.HABIT,
        scheduled_at=datetime(2026, 8, 1, 6, 0, tzinfo=UTC),
    )

    updated = await reminder_service.reschedule_event(
        db_session,
        event.id,
        datetime(2026, 8, 1, 12, 0, tzinfo=get_user_timezone("Europe/Istanbul"))
        + timedelta(minutes=10),
    )

    assert updated is not None
    assert updated.scheduled_at == datetime(2026, 8, 1, 9, 10)


async def test_created_at_stored_utc_wall_clock(db_session: AsyncSession) -> None:
    """Regression: marker timestamps must be UTC wall-clock, not Istanbul."""
    await _user(db_session)
    event = await reminder_service.create_event(
        db_session,
        user_id=1,
        bot_key=BotKey.HABIT,
        scheduled_at=datetime(2026, 8, 2, 6, 0, tzinfo=UTC),
    )

    assert event.created_at.tzinfo is None
    expected = datetime.now(UTC).replace(tzinfo=None)
    assert abs((event.created_at - expected).total_seconds()) < 60


async def test_notified_at_stored_utc_wall_clock(db_session: AsyncSession) -> None:
    """Regression: mark_notified writes a UTC wall-clock marker."""
    await _user(db_session)
    event = await reminder_service.create_event(
        db_session,
        user_id=1,
        bot_key=BotKey.HABIT,
        scheduled_at=datetime(2026, 8, 2, 6, 0, tzinfo=UTC),
    )

    assert await reminder_service.mark_notified(db_session, event.id)

    row = (
        await db_session.execute(
            text("SELECT notified_at FROM reminder_events WHERE id = :id"),
            {"id": event.id},
        )
    ).scalar_one()
    assert not row.endswith(("+", "Z"))
    stored = datetime.fromisoformat(row)
    expected = datetime.now(UTC).replace(tzinfo=None)
    assert abs((stored - expected).total_seconds()) < 60


async def test_completion_stats_window_uses_utc_not_local(db_session: AsyncSession) -> None:
    """Regression: the stats window must not shift by the user-tz offset.

    A positive event 22.5h in the past lies inside a UTC one-day window but
    outside an Istanbul-shifted one (UTC since + 3h), catching the old
    `now_in()` (Istanbul) boundary drift.
    """
    await _user(db_session)
    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    await _seed_pending(
        db_session,
        1,
        stored_at=(now - timedelta(hours=22, minutes=30)).replace(tzinfo=None).isoformat(sep=" "),
        status="positive",
    )

    stats = await habit_service.get_completion_stats(db_session, 1, days=1, now=now)

    assert stats == {"total": 1, "completed": 1}
