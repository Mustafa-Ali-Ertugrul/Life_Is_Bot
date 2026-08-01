from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from alembic import command
from app.core.config import settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _config() -> Config:
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    return cfg


def _sync_engine(db_url: str) -> Engine:
    return create_engine(db_url.replace("+aiosqlite", ""))


def test_migration_roundtrip_empty_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setattr(settings, "database_url", db_url)
    cfg = _config()

    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


def test_migration_backfills_and_cleans_duplicates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setattr(settings, "database_url", db_url)
    cfg = _config()
    command.upgrade(cfg, "c6d7e8f9a0b1")

    engine = _sync_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (timezone, language, consent_given, is_active, "
                "notifications_enabled, quiet_hours_enabled, week_start_day) "
                "VALUES ('Asia/Tokyo', 'tr', 0, 1, 1, 0, 1)"
            )
        )
        user_id = conn.execute(text("SELECT id FROM users")).scalar_one()
        for hour in (8, 9):
            conn.execute(
                text(
                    "INSERT INTO reminder_events (user_id, bot_key, related_type, related_id, "
                    "scheduled_at, status, interpretation_json, created_at) "
                    "VALUES (:u, 'habit_bot', 'habit', 1, :at, 'scheduled', '{}', :at)"
                ),
                {"u": user_id, "at": f"2026-01-05 {hour:02d}:00:00.000000"},
            )
        conn.execute(
            text(
                "INSERT INTO reminder_events (user_id, bot_key, related_type, related_id, "
                "scheduled_at, status, interpretation_json, created_at) "
                "VALUES (:u, 'habit_bot', 'habit', 2, '2026-01-05 22:00:00.000000', "
                "'notified', '{}', '2026-01-05 22:00:00.000000')"
            ),
            {"u": user_id},
        )
    engine.dispose()

    command.upgrade(cfg, "head")

    engine = _sync_engine(db_url)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, bot_key, related_id, scheduled_local_date, dedupe_key, status "
                "FROM reminder_events ORDER BY id"
            )
        ).all()
    engine.dispose()

    assert len(rows) == 3

    kept, dup, other = rows
    assert kept.dedupe_key == "habit_bot:habit:1:2026-01-05"
    assert kept.scheduled_local_date == "2026-01-05"
    assert kept.status == "scheduled"

    assert dup.status == "cancelled"
    assert dup.dedupe_key == f"habit_bot:habit:1:2026-01-05:dup:{dup.id}"

    assert other.related_id == 2
    assert other.scheduled_local_date == "2026-01-06"
    assert other.dedupe_key == "habit_bot:habit:2:2026-01-06"
    assert other.status == "notified"
