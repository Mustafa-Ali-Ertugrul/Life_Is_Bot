"""Daily SQLite backup, retention cleanup, monthly report archival."""

import asyncio
import shutil
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger("backup")


def _db_path() -> Path:
    return Path(settings.database_url.split("///")[-1])


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _copy_db(source: Path, target: Path) -> int:
    shutil.copy2(source, target)
    return target.stat().st_size


def _cleanup_backups(backup_dir: Path, cutoff: date) -> int:
    if not backup_dir.exists():
        return 0
    deleted = 0
    for f in backup_dir.glob("life_is_bot_*.db"):
        try:
            file_date = date.fromisoformat(f.stem.removeprefix("life_is_bot_"))
        except ValueError:
            continue
        if file_date < cutoff:
            f.unlink()
            deleted += 1
    return deleted


async def create_daily_backup(session: AsyncSession) -> Path | None:
    """Create a safe backup of the SQLite database.

    Strategy: WAL checkpoint (flush WAL to main DB) + file copy.
    Safe during concurrent access (bot running, WAL mode is active).
    """
    if not settings.database_url.startswith("sqlite"):
        logger.warning("backup skipped, non-sqlite database")
        return None
    backup_dir = Path(settings.backup_dir)
    await asyncio.to_thread(_ensure_dir, backup_dir)

    backup_path = backup_dir / f"life_is_bot_{date.today().isoformat()}.db"

    await session.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
    size = await asyncio.to_thread(_copy_db, _db_path(), backup_path)

    logger.info("backup created", path=str(backup_path), size=size)
    return backup_path


async def cleanup_old_backups() -> int:
    """Delete backup files older than BACKUP_RETENTION_DAYS. Returns count deleted."""
    backup_dir = Path(settings.backup_dir)
    cutoff = date.today() - timedelta(days=settings.backup_retention_days)
    deleted = await asyncio.to_thread(_cleanup_backups, backup_dir, cutoff)

    if deleted:
        logger.info("backup cleanup", deleted=deleted, cutoff=cutoff.isoformat())
    return deleted


async def save_monthly_report_file(content: str, year: int, month: int, user_id: int) -> Path:
    """Save monthly report as markdown file (one file per user)."""
    reports_dir = Path(settings.reports_dir)
    await asyncio.to_thread(_ensure_dir, reports_dir)

    path = reports_dir / f"monthly_report_{year}-{month:02d}_user{user_id}.md"
    await asyncio.to_thread(path.write_text, content, encoding="utf-8")

    logger.info("monthly report saved", path=str(path))
    return path
