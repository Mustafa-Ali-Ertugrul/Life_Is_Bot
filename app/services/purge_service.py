"""Monthly data purge: FK-safe deletion of historical data + SQLite vacuum."""

import asyncio
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logger import get_logger
from app.models import AuditLog, NotificationLog, ReminderEvent, StepLog, UserResponse

logger = get_logger("purge")


@dataclass(frozen=True)
class PurgeStats:
    user_responses: int = 0
    notification_logs: int = 0
    reminder_events: int = 0
    step_logs: int = 0
    audit_logs: int = 0


def cutoff_date_for(today: date, retention_months: int) -> date:
    """First day of the month that is ``retention_months`` before ``today``'s month."""
    idx = today.year * 12 + (today.month - 1) - retention_months
    return date(idx // 12, idx % 12 + 1, 1)


def _cutoff_datetime(cutoff_date: date) -> datetime:
    return datetime.combine(cutoff_date, time.min, tzinfo=UTC)


def _db_path() -> Path:
    return Path(settings.database_url.split("///")[-1])


def _db_size() -> int | None:
    path = _db_path()
    try:
        return path.stat().st_size
    except FileNotFoundError:
        return None


async def purge_old_data(session: AsyncSession, today: date) -> PurgeStats:
    """Delete data older than the retention cutoff, in FK-safe order.

    Order: user_responses -> notification_logs -> reminder_events ->
    step_logs -> audit_logs. Event-linked rows are deleted by the parent
    event's cutoff so referential integrity is preserved even with SQLite
    foreign_keys pragma disabled.
    """
    cutoff = cutoff_date_for(today, settings.data_retention_months)
    cutoff_dt = _cutoff_datetime(cutoff)

    old_event_ids = select(ReminderEvent.id).where(ReminderEvent.scheduled_local_date < cutoff)

    stats = PurgeStats()
    stats.user_responses = await _delete(
        session,
        delete(UserResponse).where(UserResponse.reminder_event_id.in_(old_event_ids)),
    )
    stats.notification_logs = await _delete(
        session,
        delete(NotificationLog).where(NotificationLog.reminder_event_id.in_(old_event_ids)),
    )
    stats.notification_logs += await _delete(
        session,
        delete(NotificationLog).where(
            NotificationLog.reminder_event_id.is_(None),
            NotificationLog.sent_at < cutoff_dt,
        ),
    )
    stats.reminder_events = await _delete(
        session,
        delete(ReminderEvent).where(ReminderEvent.scheduled_local_date < cutoff),
    )
    stats.step_logs = await _delete(
        session,
        delete(StepLog).where(StepLog.log_date < cutoff),
    )
    stats.audit_logs = await _delete(
        session,
        delete(AuditLog).where(AuditLog.created_at < cutoff_dt),
    )

    logger.info(
        "purge executed",
        cutoff=cutoff.isoformat(),
        **asdict(stats),
    )
    return stats


async def _delete(session: AsyncSession, statement: object) -> int:
    result = await session.execute(statement)  # type: ignore[arg-type]
    return int(result.rowcount or 0)


def _vacuum(path: Path) -> int:
    conn = sqlite3.connect(path, isolation_level=None, timeout=30.0)
    try:
        conn.execute("VACUUM")
    finally:
        conn.close()
    return path.stat().st_size


async def vacuum_database() -> int | None:
    """Run VACUUM on a raw autocommit connection; best-effort on lock errors."""
    if not settings.database_url.startswith("sqlite"):
        logger.warning("vacuum skipped, non-sqlite database")
        return None
    path = _db_path()
    try:
        size = await asyncio.to_thread(_vacuum, path)
    except sqlite3.Error:
        logger.warning("vacuum failed", exc_info=True)
        return None
    logger.info("vacuum completed", size=size)
    return size


__all__ = [
    "PurgeStats",
    "cutoff_date_for",
    "purge_old_data",
    "vacuum_database",
]
