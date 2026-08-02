from datetime import date
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from alembic import command
from app.core.config import settings
from app.models.step_log import StepLog
from app.models.step_settings import StepSettings
from app.models.user import User

PROJECT_ROOT = Path(__file__).resolve().parents[1]

STEP_SETTINGS_INSERT = (
    "INSERT INTO step_settings (user_id, daily_target, reminder_hour, reminder_minute, "
    "days_of_week, is_active) VALUES (1, :target, :hour, :minute, '1,2,3,4,5,6,7', 1)"
)

STEP_LOG_INSERT = (
    "INSERT INTO step_logs (user_id, log_date, steps, source) "
    "VALUES (1, :log_date, :steps, 'manual')"
)


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


async def test_step_settings_negative_target_rejected(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    settings = StepSettings(
        user_id=user.id,
        daily_target=-1,
        reminder_hour=21,
        reminder_minute=0,
        days_of_week="1,2,3,4,5,6,7",
        is_active=True,
    )
    db_session.add(settings)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_step_settings_target_above_max_rejected(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    settings = StepSettings(
        user_id=user.id,
        daily_target=100001,
        reminder_hour=21,
        reminder_minute=0,
        days_of_week="1,2,3,4,5,6,7",
        is_active=True,
    )
    db_session.add(settings)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_step_settings_hour_out_of_range_rejected(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    settings = StepSettings(
        user_id=user.id,
        daily_target=8000,
        reminder_hour=24,
        reminder_minute=0,
        days_of_week="1,2,3,4,5,6,7",
        is_active=True,
    )
    db_session.add(settings)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_step_settings_minute_out_of_range_rejected(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    settings = StepSettings(
        user_id=user.id,
        daily_target=8000,
        reminder_hour=21,
        reminder_minute=60,
        days_of_week="1,2,3,4,5,6,7",
        is_active=True,
    )
    db_session.add(settings)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_step_log_negative_steps_rejected(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    log = StepLog(user_id=user.id, log_date=date(2026, 8, 2), steps=-1, source="manual")
    db_session.add(log)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_step_log_steps_above_max_rejected(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    log = StepLog(user_id=user.id, log_date=date(2026, 8, 2), steps=200001, source="manual")
    db_session.add(log)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_step_log_duplicate_user_date_rejected(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    first = StepLog(user_id=user.id, log_date=date(2026, 8, 2), steps=7000, source="manual")
    db_session.add(first)
    await db_session.commit()

    second = StepLog(user_id=user.id, log_date=date(2026, 8, 2), steps=8000, source="manual")
    db_session.add(second)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_step_boundary_values_accepted(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    settings = StepSettings(
        user_id=user.id,
        daily_target=0,
        reminder_hour=0,
        reminder_minute=0,
        days_of_week="1,2,3,4,5,6,7",
        is_active=True,
    )
    db_session.add(settings)
    await db_session.commit()

    log = StepLog(user_id=user.id, log_date=date(2026, 8, 2), steps=0, source="manual")
    db_session.add(log)
    await db_session.commit()


def test_migration_step_tables_upgrade_downgrade_cycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setattr(settings, "database_url", db_url)
    cfg = _config()

    command.upgrade(cfg, "head")

    engine = _sync_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (timezone, language, consent_given, is_active, "
                "notifications_enabled, quiet_hours_enabled, week_start_day) "
                "VALUES ('Europe/Istanbul', 'tr', 1, 1, 1, 0, 1)"
            )
        )
        with pytest.raises(IntegrityError):
            conn.execute(
                text(STEP_SETTINGS_INSERT),
                {"target": 8000, "hour": 24, "minute": 0},
            )
    engine.dispose()

    engine = _sync_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            text(STEP_SETTINGS_INSERT),
            {"target": 8000, "hour": 21, "minute": 0},
        )
        with pytest.raises(IntegrityError):
            conn.execute(
                text(STEP_LOG_INSERT),
                {"log_date": "2026-08-02", "steps": 200001},
            )
        conn.execute(
            text(STEP_LOG_INSERT),
            {"log_date": "2026-08-02", "steps": 7000},
        )
        with pytest.raises(IntegrityError):
            conn.execute(
                text(STEP_LOG_INSERT),
                {"log_date": "2026-08-02", "steps": 8000},
            )
    engine.dispose()

    command.downgrade(cfg, "c5d6e7f8b9a0")

    engine = _sync_engine(db_url)
    with engine.begin() as conn:
        step_settings_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'step_settings'")
        ).scalar_one_or_none()
        step_logs_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'step_logs'")
        ).scalar_one_or_none()
        assert step_settings_exists is None
        assert step_logs_exists is None
    engine.dispose()

    command.upgrade(cfg, "head")

    engine = _sync_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (timezone, language, consent_given, is_active, "
                "notifications_enabled, quiet_hours_enabled, week_start_day) "
                "VALUES ('Europe/Istanbul', 'tr', 1, 1, 1, 0, 1)"
            )
        )
        with pytest.raises(IntegrityError):
            conn.execute(
                text(STEP_SETTINGS_INSERT),
                {"target": 100001, "hour": 21, "minute": 0},
            )
    engine.dispose()
