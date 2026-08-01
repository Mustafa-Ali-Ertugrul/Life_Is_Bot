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
from app.models.supplement_plan import SupplementPlan
from app.models.user import User

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SUPPLEMENT_INSERT = (
    "INSERT INTO supplement_plans (user_id, name, with_food, target_hour, target_minute, "
    "days_of_week, is_active) VALUES (1, :name, :with_food, :hour, :minute, '1,3,5', 1)"
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


async def test_supplement_plan_hour_out_of_range_rejected(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    plan = SupplementPlan(
        user_id=user.id,
        name="D Vitamini",
        with_food="any",
        target_hour=24,
        target_minute=0,
        days_of_week="1,3,5",
        is_active=True,
    )
    db_session.add(plan)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_supplement_plan_negative_hour_rejected(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    plan = SupplementPlan(
        user_id=user.id,
        name="D Vitamini",
        with_food="any",
        target_hour=-1,
        target_minute=0,
        days_of_week="1,3,5",
        is_active=True,
    )
    db_session.add(plan)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_supplement_plan_minute_out_of_range_rejected(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    plan = SupplementPlan(
        user_id=user.id,
        name="D Vitamini",
        with_food="any",
        target_hour=8,
        target_minute=60,
        days_of_week="1,3,5",
        is_active=True,
    )
    db_session.add(plan)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_supplement_plan_negative_minute_rejected(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    plan = SupplementPlan(
        user_id=user.id,
        name="D Vitamini",
        with_food="any",
        target_hour=8,
        target_minute=-1,
        days_of_week="1,3,5",
        is_active=True,
    )
    db_session.add(plan)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_supplement_plan_invalid_with_food_rejected(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    plan = SupplementPlan(
        user_id=user.id,
        name="D Vitamini",
        with_food="breakfast",
        target_hour=8,
        target_minute=0,
        days_of_week="1,3,5",
        is_active=True,
    )
    db_session.add(plan)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_supplement_plan_inverted_date_range_rejected(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    plan = SupplementPlan(
        user_id=user.id,
        name="D Vitamini",
        with_food="any",
        target_hour=8,
        target_minute=0,
        days_of_week="1,3,5",
        is_active=True,
        start_date=date(2026, 8, 10),
        end_date=date(2026, 8, 1),
    )
    db_session.add(plan)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_supplement_plan_boundary_values_accepted(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    for hour, minute in ((0, 0), (23, 59)):
        plan = SupplementPlan(
            user_id=user.id,
            name="D Vitamini",
            with_food="full",
            target_hour=hour,
            target_minute=minute,
            days_of_week="1,3,5",
            is_active=True,
            start_date=None,
            end_date=None,
        )
        db_session.add(plan)
        await db_session.commit()


def test_migration_supplement_plan_check_constraints_upgrade_downgrade_cycle(
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
                text(SUPPLEMENT_INSERT),
                {"name": "D Vitamini", "with_food": "any", "hour": 24, "minute": 0},
            )
    engine.dispose()

    engine = _sync_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            text(SUPPLEMENT_INSERT),
            {"name": "D Vitamini", "with_food": "full", "hour": 23, "minute": 59},
        )
    engine.dispose()

    command.downgrade(cfg, "b4c5d6e7f8a9")

    engine = _sync_engine(db_url)
    with engine.begin() as conn:
        table_exists = conn.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'supplement_plans'"
            )
        ).scalar_one_or_none()
        assert table_exists is None
    engine.dispose()

    command.upgrade(cfg, "head")

    engine = _sync_engine(db_url)
    with engine.begin() as conn:
        with pytest.raises(IntegrityError):
            conn.execute(
                text(SUPPLEMENT_INSERT),
                {"name": "Kötü", "with_food": "any", "hour": 24, "minute": 0},
            )
    engine.dispose()
