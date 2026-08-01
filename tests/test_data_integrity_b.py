from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from alembic import command
from app.core.config import settings
from app.models.habit import Habit
from app.models.user import User

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _config() -> Config:
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    return cfg


def _sync_engine(db_url: str) -> Engine:
    return create_engine(db_url.replace("+aiosqlite", ""))


async def _user(db_session: AsyncSession) -> User:
    user = User(
        name="Test",
        timezone="Europe/Istanbul",
        language="tr",
        consent_given=True,
        is_active=True,
        notifications_enabled=True,
        quiet_hours_enabled=False,
        week_start_day=1,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def test_habit_hour_out_of_range_rejected(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    habit = Habit(
        user_id=user.id,
        name="H",
        target_hour=24,
        target_minute=0,
        days_of_week="1,2,3,4,5,6,7",
        is_active=True,
    )
    db_session.add(habit)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_habit_minute_out_of_range_rejected(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    habit = Habit(
        user_id=user.id,
        name="H",
        target_hour=8,
        target_minute=60,
        days_of_week="1,2,3,4,5,6,7",
        is_active=True,
    )
    db_session.add(habit)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_habit_boundary_values_accepted(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    habit = Habit(
        user_id=user.id,
        name="H",
        target_hour=23,
        target_minute=59,
        days_of_week="1,2,3,4,5,6,7",
        is_active=True,
    )
    db_session.add(habit)
    await db_session.commit()


async def test_user_week_start_day_out_of_range_rejected(db_session: AsyncSession) -> None:
    user = User(
        name="Test",
        timezone="Europe/Istanbul",
        language="tr",
        consent_given=True,
        is_active=True,
        notifications_enabled=True,
        quiet_hours_enabled=False,
        week_start_day=0,
    )
    db_session.add(user)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_user_quiet_hours_invalid_format_rejected(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    user.quiet_hours_start = "8:00"
    user.quiet_hours_end = "23:00"
    user.quiet_hours_enabled = True
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_user_quiet_hours_valid_format_accepted(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    user.quiet_hours_start = "08:00"
    user.quiet_hours_end = "23:00"
    user.quiet_hours_enabled = True
    await db_session.commit()


def test_migration_b_preserves_data_and_enforces_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setattr(settings, "database_url", db_url)
    cfg = _config()

    command.upgrade(cfg, "d1e2f3a4b5c6")

    engine = _sync_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (timezone, language, consent_given, is_active, "
                "notifications_enabled, quiet_hours_enabled, week_start_day) "
                "VALUES ('Europe/Istanbul', 'tr', 1, 1, 1, 0, 1)"
            )
        )
        user_id = conn.execute(text("SELECT id FROM users")).scalar_one()
        conn.execute(
            text(
                "INSERT INTO reminder_events (user_id, bot_key, scheduled_at, status, "
                "interpretation_json, created_at) "
                "VALUES (:u, 'core_bot', '2026-01-05 08:00:00.000000', 'scheduled', '{}', "
                "'2026-01-05 08:00:00.000000')"
            ),
            {"u": user_id},
        )
        conn.execute(
            text(
                "INSERT INTO habits (user_id, name, target_hour, target_minute, "
                "days_of_week, is_active) "
                "VALUES (:u, 'Su iç', 8, 0, '1,2,3,4,5,6,7', 1)"
            ),
            {"u": user_id},
        )
    engine.dispose()

    command.upgrade(cfg, "head")

    engine = _sync_engine(db_url)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT scheduled_local_date, dedupe_key FROM reminder_events")
        ).one()
        assert row.scheduled_local_date == "1970-01-01"
        assert row.dedupe_key == "legacy"

        conn.execute(
            text(
                "INSERT INTO reminder_events (user_id, bot_key, scheduled_at, status, "
                "interpretation_json, scheduled_local_date, dedupe_key) "
                "VALUES (1, 'core_bot', '2026-01-05 09:00:00.000000', 'scheduled', '{}', "
                "'2026-01-05', 'core_bot:none:0:2026-01-05')"
            )
        )
        created_at = conn.execute(
            text("SELECT created_at FROM reminder_events ORDER BY id DESC LIMIT 1")
        ).scalar_one()
        assert created_at is not None

        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO habits (user_id, name, target_hour, target_minute, "
                    "days_of_week, is_active) "
                    "VALUES (1, 'Kötü', 24, 0, '1', 1)"
                )
            )
    engine.dispose()
