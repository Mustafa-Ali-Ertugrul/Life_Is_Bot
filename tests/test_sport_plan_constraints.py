from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from alembic import command
from app.core.config import settings
from app.models.sport_plan import SportPlan
from app.models.user import User

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SPORT_INSERT = (
    "INSERT INTO sport_plans (user_id, sport_type, target_hour, target_minute, "
    "days_of_week, is_active) VALUES (1, :sport_type, :hour, :minute, '1,3,5', 1)"
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


async def test_sport_plan_hour_out_of_range_rejected(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    plan = SportPlan(
        user_id=user.id,
        sport_type="Koşu",
        target_hour=24,
        target_minute=0,
        days_of_week="1,3,5",
        is_active=True,
    )
    db_session.add(plan)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_sport_plan_negative_hour_rejected(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    plan = SportPlan(
        user_id=user.id,
        sport_type="Koşu",
        target_hour=-1,
        target_minute=0,
        days_of_week="1,3,5",
        is_active=True,
    )
    db_session.add(plan)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_sport_plan_minute_out_of_range_rejected(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    plan = SportPlan(
        user_id=user.id,
        sport_type="Koşu",
        target_hour=8,
        target_minute=60,
        days_of_week="1,3,5",
        is_active=True,
    )
    db_session.add(plan)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_sport_plan_negative_minute_rejected(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    plan = SportPlan(
        user_id=user.id,
        sport_type="Koşu",
        target_hour=8,
        target_minute=-1,
        days_of_week="1,3,5",
        is_active=True,
    )
    db_session.add(plan)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_sport_plan_boundary_values_accepted(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    for hour, minute in ((0, 0), (23, 59)):
        plan = SportPlan(
            user_id=user.id,
            sport_type="Koşu",
            target_hour=hour,
            target_minute=minute,
            days_of_week="1,3,5",
            is_active=True,
        )
        db_session.add(plan)
        await db_session.commit()


def test_migration_sport_plan_check_constraints_upgrade_downgrade_cycle(
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
            conn.execute(text(SPORT_INSERT), {"sport_type": "Koşu", "hour": 24, "minute": 0})
    engine.dispose()

    engine = _sync_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text(SPORT_INSERT), {"sport_type": "Koşu", "hour": 23, "minute": 59})
    engine.dispose()

    command.downgrade(cfg, "a3b4c5d6e7f8")

    engine = _sync_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text(SPORT_INSERT), {"sport_type": "Kötü", "hour": 24, "minute": 0})
        conn.execute(text("DELETE FROM sport_plans WHERE sport_type = 'Kötü'"))
    engine.dispose()

    command.upgrade(cfg, "head")

    engine = _sync_engine(db_url)
    with engine.begin() as conn:
        with pytest.raises(IntegrityError):
            conn.execute(text(SPORT_INSERT), {"sport_type": "Kötü", "hour": 24, "minute": 0})
    engine.dispose()
