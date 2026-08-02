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
from app.models.medication_plan import MedicationPlan
from app.models.user import User
from app.services import medication_service

PROJECT_ROOT = Path(__file__).resolve().parents[1]

MEDICATION_INSERT = (
    "INSERT INTO medication_plans (user_id, name, with_food, target_hour, target_minute, "
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


def _plan(
    user_id: int,
    *,
    with_food: str = "any",
    target_hour: int = 8,
    target_minute: int = 0,
    days_of_week: str = "1,3,5",
    **kwargs: object,
) -> MedicationPlan:
    return MedicationPlan(
        user_id=user_id,
        name="Metformin",
        with_food=with_food,
        target_hour=target_hour,
        target_minute=target_minute,
        days_of_week=days_of_week,
        is_active=True,
        **kwargs,
    )


async def test_medication_plan_defaults(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    plan = MedicationPlan(
        user_id=user.id,
        name="Metformin",
        target_hour=8,
        target_minute=0,
        days_of_week="1,2,3,4,5,6,7",
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)

    assert plan.with_food == "any"
    assert plan.days_of_week == "1,2,3,4,5,6,7"
    assert plan.is_active is True


async def test_medication_plan_hour_out_of_range_rejected(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    db_session.add(_plan(user.id, target_hour=24))
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_medication_plan_minute_out_of_range_rejected(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    db_session.add(_plan(user.id, target_minute=60))
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_medication_plan_invalid_with_food_rejected(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    db_session.add(_plan(user.id, with_food="breakfast"))
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_medication_plan_inverted_date_range_rejected(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    db_session.add(
        _plan(
            user.id,
            start_date=date(2026, 8, 10),
            end_date=date(2026, 8, 1),
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_medication_plan_null_dates_accepted(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    db_session.add(_plan(user.id, start_date=None, end_date=None))
    await db_session.commit()


async def test_medication_plan_long_notes_accepted(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    db_session.add(_plan(user.id, notes="x" * 500))
    await db_session.commit()


async def test_medication_plan_cascade_delete_with_user(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    plan = await medication_service.create_medication_plan(
        db_session, user.id, "Metformin", 8, 0, "1,2,3,4,5,6,7"
    )

    await db_session.delete(user)
    await db_session.commit()

    assert await medication_service.get_medication_plan(db_session, plan.id) is None


def test_migration_medication_plan_check_constraints_upgrade_downgrade_cycle(
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
                text(MEDICATION_INSERT),
                {"name": "Metformin", "with_food": "any", "hour": 24, "minute": 0},
            )
    engine.dispose()

    engine = _sync_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            text(MEDICATION_INSERT),
            {"name": "Metformin", "with_food": "full", "hour": 23, "minute": 59},
        )
    engine.dispose()

    command.downgrade(cfg, "e8a9f0b1c2d3")

    engine = _sync_engine(db_url)
    with engine.begin() as conn:
        table_exists = conn.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'medication_plans'"
            )
        ).scalar_one_or_none()
        assert table_exists is None
    engine.dispose()

    command.upgrade(cfg, "head")

    engine = _sync_engine(db_url)
    with engine.begin() as conn:
        with pytest.raises(IntegrityError):
            conn.execute(
                text(MEDICATION_INSERT),
                {"name": "Kötü", "with_food": "any", "hour": 24, "minute": 0},
            )
    engine.dispose()
