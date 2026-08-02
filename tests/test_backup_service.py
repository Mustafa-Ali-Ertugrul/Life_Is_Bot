"""Backup service and scheduler job tests."""

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from telegram import Bot

from app import models  # noqa: F401
from app.core.config import settings
from app.core.database import Base
from app.models import BotKey, ReminderEvent, ReminderStatus, TelegramAccount, User
from app.scheduler import engine, jobs
from app.services import backup_service


async def _file_session(tmp_path: Path) -> tuple[AsyncSession, Path]:
    """Build a session backed by a real SQLite file (in-memory cannot be copied)."""
    src = tmp_path / "src.db"
    engine_factory = create_async_engine(
        f"sqlite+aiosqlite:///{src}", connect_args={"check_same_thread": False}
    )
    async with engine_factory.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine_factory, expire_on_commit=False)
    return factory(), src


def _patch_sqlite(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{tmp_path / 'src.db'}")
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path / "backups"))


async def test_create_daily_backup_creates_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session, _ = await _file_session(tmp_path)
    _patch_sqlite(monkeypatch, tmp_path)
    async with session:
        path = await backup_service.create_daily_backup(session)
    assert path is not None and path.exists()
    assert path.name == f"life_is_bot_{date.today().isoformat()}.db"


async def test_backup_is_valid_sqlite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import sqlite3

    session, _ = await _file_session(tmp_path)
    _patch_sqlite(monkeypatch, tmp_path)
    async with session:
        path = await backup_service.create_daily_backup(session)
    assert path is not None
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT 1").fetchone() == (1,)
    conn.close()


async def test_backup_dir_created_if_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session, _ = await _file_session(tmp_path)
    target = tmp_path / "nested" / "backups"
    _patch_sqlite(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "backup_dir", str(target))
    async with session:
        await backup_service.create_daily_backup(session)
    assert target.exists()


async def test_cleanup_deletes_old(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path))
    monkeypatch.setattr(settings, "backup_retention_days", 30)
    old = tmp_path / f"life_is_bot_{(date.today() - timedelta(days=35)).isoformat()}.db"
    new = tmp_path / f"life_is_bot_{date.today().isoformat()}.db"
    old.write_text("old")
    new.write_text("new")

    assert await backup_service.cleanup_old_backups() == 1
    assert not old.exists()
    assert new.exists()


async def test_cleanup_keeps_recent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path))
    (tmp_path / f"life_is_bot_{date.today().isoformat()}.db").write_text("new")

    assert await backup_service.cleanup_old_backups() == 0


async def test_cleanup_missing_dir_returns_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path / "yok"))

    assert await backup_service.cleanup_old_backups() == 0


async def test_save_monthly_report_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "reports_dir", str(tmp_path / "reports"))

    path = await backup_service.save_monthly_report_file("# Rapor", 2026, 8, 42)
    assert path.name == "monthly_report_2026-08_user42.md"
    assert path.read_text(encoding="utf-8") == "# Rapor"


async def test_backup_job_skips_when_disabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(settings, "backup_enabled", False)
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path / "backups"))

    await jobs.daily_backup_job()
    assert not (tmp_path / "backups").exists()


async def test_monthly_report_job_skips_before_last_day(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(settings, "auto_monthly_report", True)
    monkeypatch.setattr(settings, "reports_dir", str(tmp_path / "reports"))
    monkeypatch.setattr(jobs, "now_in", lambda *a: datetime(2026, 8, 15, 23, 50, tzinfo=UTC))

    await jobs.monthly_report_job()
    assert not (tmp_path / "reports").exists()


async def test_monthly_report_job_last_day_saves_and_sends(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, db_session: AsyncSession
) -> None:
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _uow() -> AsyncIterator[AsyncSession]:
        yield db_session

    monkeypatch.setattr(settings, "auto_monthly_report", True)
    monkeypatch.setattr(settings, "reports_dir", str(tmp_path / "reports"))
    monkeypatch.setattr(jobs, "unit_of_work", _uow)
    monkeypatch.setattr(jobs, "now_in", lambda *a: datetime(2026, 8, 31, 23, 50, tzinfo=UTC))
    monkeypatch.setattr(engine, "_bot", Bot(token="test"))

    user = User(name="test", consent_given=True, is_active=True, timezone="Europe/Istanbul")
    db_session.add(user)
    await db_session.flush()
    db_session.add(TelegramAccount(user_id=user.id, telegram_user_id="777000"))
    await db_session.flush()
    db_session.add(
        ReminderEvent(
            user_id=user.id,
            bot_key=BotKey.HABIT.value,
            related_type="su_ic",
            related_id=None,
            scheduled_at=datetime(2026, 8, 31, 20, 0, tzinfo=UTC),
            scheduled_local_date=date(2026, 8, 31),
            dedupe_key="monthly-test:1",
            status=ReminderStatus.POSITIVE.value,
        )
    )
    await db_session.flush()

    sent: list[str] = []

    async def _fake_send(bot: object, chat_id: str, text: str) -> str:
        sent.append(chat_id)
        return "1"

    monkeypatch.setattr(jobs, "send_plain_text", _fake_send)

    await jobs.monthly_report_job()

    report_file = tmp_path / "reports" / f"monthly_report_2026-08_user{user.id}.md"
    assert report_file.exists()
    content = report_file.read_text(encoding="utf-8")
    assert "Genel tamamlama: 100.0% (1/1)" in content
    assert sent == ["777000"]
